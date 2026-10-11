"""Assemble the report contract consumed by the dashboard and future agents."""

import pandas as pd

from backend.app.data import Books
from .cashflow import cash_balance, receivables
from .expenses import expense_changes, monthly_summary, recurring_charges
from .jobs import job_profitability, losing_jobs, margin_by_job_type


def build_report(
    books: Books, month: str | None = None, *, is_sample=False, dataset_revision=""
) -> dict:
    months = [
        str(period)
        for period in pd.period_range(
            books.business["opening_balance_date"][:7],
            books.business["as_of_date"][:7],
            freq="M",
        )
    ]
    selected = months[-1] if month is None else month
    if month is None and len(months) > 1 and not monthly_summary(books, selected)["period_complete"]:
        selected = months[-2]  # real bank data ends mid-month; default to the last whole month
    if selected not in months:
        raise ValueError("month must be YYYY-MM within the books' opening/as-of window")
    index = months.index(selected)
    previous = monthly_summary(books, months[index - 1]) if index else None
    if previous is not None and not previous["period_complete"]:
        previous = None
    return {
        "business": books.business.copy(),
        "month": selected,
        "months": months,
        "is_sample": is_sample,
        "dataset_revision": dataset_revision,
        "previous_summary": previous,
        "narrative": None,
        "monthly_summary": monthly_summary(books, selected),
        "expense_changes": expense_changes(books, selected),
        "recurring_charges": recurring_charges(books, selected),
        "job_profitability": job_profitability(books, selected),
        "losing_jobs": losing_jobs(books, selected),
        "margin_by_job_type": margin_by_job_type(books, selected),
        "cash_balance": cash_balance(books),
        "receivables": receivables(books),
    }
