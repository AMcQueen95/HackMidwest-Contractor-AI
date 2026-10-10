"""The finance functions the agents call.

Each function comes from app.finance when it exists there, otherwise from
stub_books. That lets the agents run before the finance layer is done, and
each real function replaces its stub as soon as it lands.

Contract for app.finance (every function returns a JSON-serializable dict):

  expenses.monthly_summary(month: str)    month is "YYYY-MM"
  expenses.expense_changes(month: str)    category changes vs the prior month
  expenses.recurring_charges()            subscriptions and duplicate tools
  jobs.job_profitability(job_id: str)     one job's revenue, costs, margin
  jobs.losing_jobs()                      jobs with negative profit
  jobs.margin_by_job_type()               margin per job type
  cashflow.cash_balance()                 cash on hand as of the books date
  cashflow.receivables()                  unpaid invoices with aging
  cashflow.affordability(amount: float)   can we spend this much now
"""

import importlib

from app.agents import stub_books


def _resolve(module: str, name: str):
    try:
        return getattr(importlib.import_module(f"app.finance.{module}"), name)
    except (ImportError, AttributeError):
        return getattr(stub_books, name)


monthly_summary = _resolve("expenses", "monthly_summary")
expense_changes = _resolve("expenses", "expense_changes")
recurring_charges = _resolve("expenses", "recurring_charges")

job_profitability = _resolve("jobs", "job_profitability")
losing_jobs = _resolve("jobs", "losing_jobs")
margin_by_job_type = _resolve("jobs", "margin_by_job_type")

cash_balance = _resolve("cashflow", "cash_balance")
receivables = _resolve("cashflow", "receivables")
affordability = _resolve("cashflow", "affordability")


def using_stubs() -> list[str]:
    """Names of functions still served by stub_books."""
    return [
        name
        for name, fn in globals().items()
        if callable(fn) and getattr(fn, "__module__", "") == stub_books.__name__
    ]
