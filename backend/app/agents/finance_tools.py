"""Strands tools that give the agents read access to the books.

Each tool wraps a function from backend.app.finance and binds the active
Books, so the model only passes question parameters like a month or a dollar
amount. The docstrings are what the model reads to choose a tool, so keep
them specific.
"""

from datetime import date, timedelta

from strands import tool

from backend.app.agents.events import emit

from backend.app import finance
from backend.app.data import Books, load_books
from backend.app.agent_context import active_books

_books: Books | None = None


def get_books() -> Books:
    """The dataset the agents read (bundled sample until use_books is called)."""
    if (books := active_books.get()) is not None:
        return books
    global _books
    if _books is None:
        _books = load_books()
    return _books


def use_books(books: Books) -> None:
    """Point the agents at a new dataset, e.g. after a validated upload."""
    global _books
    _books = books


def _card(name: str, result: dict) -> dict:
    """Show this result as a card in the chat (no-op outside a streamed answer)."""
    emit({"type": "card", "card": {"type": name, "data": result}})
    return result


def latest_full_month(books: Books) -> str:
    as_of = date.fromisoformat(books.business["as_of_date"])
    month_end = (as_of + timedelta(days=1)).day == 1
    last = as_of if month_end else as_of.replace(day=1) - timedelta(days=1)
    return last.strftime("%Y-%m")


# --- Shared -------------------------------------------------------------------

@tool
def business_profile() -> dict:
    """Get the business name, the books' as-of date and the latest full month of
    data. Call this first to work out what "this month" or "last month" means."""
    books = get_books()
    b = books.business
    return {"name": b["name"], "currency": b["currency"], "accounting_basis": b["accounting_basis"],
            "data_starts": b["opening_balance_date"], "as_of_date": b["as_of_date"],
            "latest_full_month": latest_full_month(books)}


@tool
def monthly_summary(month: str) -> dict:
    """Get cash-basis revenue, expenses, profit and spending by category for one month.

    Args:
        month: Month as YYYY-MM, e.g. "2026-09".
    """
    return finance.monthly_summary(get_books(), month)


# --- Expense agent --------------------------------------------------------------

@tool
def expense_changes(month: str, previous_month: str | None = None) -> dict:
    """Compare spending by category against an earlier month, with dollar and
    percent change for each category.

    Args:
        month: The month to analyze, YYYY-MM.
        previous_month: The month to compare against, YYYY-MM. Defaults to the month before.
    """
    return _card("expense_changes", finance.expense_changes(get_books(), month, previous_month))


@tool
def recurring_charges(month: str | None = None) -> dict:
    """List recurring bills (same vendor and category in at least two months)
    and groups of vendors that may overlap. Each overlap group lists every
    vendor's own monthly cost and what cancelling that one vendor would save.
    Use it to spot duplicate or unused subscriptions.

    Args:
        month: Reporting month, YYYY-MM. Defaults to the latest month.
    """
    books = get_books()
    result = finance.recurring_charges(books, month)
    for group in result.get("potential_duplicate_groups", []):
        group["vendor_monthly_costs"] = [
            {"vendor": v, "monthly_cost": _vendor_spend(books, result["month"], group["category"], v),
             "saving_if_cancelled": _vendor_spend(books, result["month"], group["category"], v)}
            for v in group["vendors"]]
        group["note"] = ("monthly_total is all of these vendors together. Cancelling one vendor saves "
                         "only that vendor's saving_if_cancelled.")
    return result


def _vendor_spend(books: Books, month: str, category: str, vendor: str) -> float:
    """What one vendor was paid in one category and month, in dollars."""
    t = books.transactions
    rows = t[(t["date"].astype(str).str.startswith(month)) & (t["vendor"] == vendor)
             & (t["category"].str.lower() == category.lower()) & (t["_amount_cents"] < 0)]
    return -int(rows["_amount_cents"].sum()) / 100


# --- Job profitability agent ----------------------------------------------------

@tool
def job_profitability(month: str | None = None) -> dict:
    """List jobs with quoted revenue, cash received, direct costs (materials,
    permits, rentals), labor cost, profit and margin.

    Args:
        month: Only jobs completed in this month, YYYY-MM. Omit for all jobs.
    """
    return finance.job_profitability(get_books(), month)


@tool
def losing_jobs(month: str | None = None) -> dict:
    """List only the jobs that lost money, with the same cost breakdown.

    Args:
        month: Only jobs completed in this month, YYYY-MM. Omit for all jobs.
    """
    return _card("losing_jobs", finance.losing_jobs(get_books(), month))


@tool
def margin_by_job_type(month: str | None = None) -> dict:
    """Get job counts, totals and weighted margin for each job type (AC repair,
    water heater install, and so on).

    Args:
        month: Only jobs completed in this month, YYYY-MM. Omit for all jobs.
    """
    return finance.margin_by_job_type(get_books(), month)


# --- Cash flow agent -------------------------------------------------------------

@tool
def cash_balance() -> dict:
    """Get the bank balance, the tax hold set aside, and cash available after it."""
    return finance.cash_balance(get_books())


@tool
def receivables() -> dict:
    """List unpaid invoices: total outstanding, overdue total, aging buckets, and
    amounts by customer and by invoice."""
    return _card("receivables", finance.receivables(get_books()))


@tool
def affordability(amount: float, reserve_months: int = 1) -> dict:
    """Check whether the business can pay for a purchase in cash and still keep
    the tax hold plus a cushion of recent monthly expenses. Also returns a
    scenario where every unpaid invoice gets collected first.

    Args:
        amount: Purchase price in dollars.
        reserve_months: Months of expenses to keep as a cushion. Defaults to 1.
    """
    return _card("affordability", finance.affordability(get_books(), amount, reserve_months=reserve_months))
