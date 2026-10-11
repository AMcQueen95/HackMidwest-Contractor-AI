"""Can the business afford another employee, and what growth would pay for one?

Everything comes from the books: recent months' revenue, spending and profit,
cash above the purchase reserve, and the margin left after job costs. The one
assumption, employer costs on top of wages, is a parameter and is reported.
"""

import pandas as pd

from backend.app.data import Books
from .cashflow import affordability
from .expenses import monthly_summary
from .jobs import job_profitability

HOURS_PER_MONTH = 40 * 52 / 12  # full time
VARIABLE = {"materials", "subcontractors", "permits", "fuel", "equipment"}  # costs that grow with the work


def _complete_months(books: Books) -> list[str]:
    months = [str(p) for p in pd.period_range(books.business["opening_balance_date"][:7],
                                              books.business["as_of_date"][:7], freq="M")]
    return [m for m in months if monthly_summary(books, m)["period_complete"]]


def hire_capacity(books: Books, monthly_cost: float | None = None, burden_rate: float = 0.20) -> dict:
    """How much a new hire the business can afford from its profit, how long spare cash covers
    one, and the extra revenue a hire must bring in to keep profit where it is.

    monthly_cost is the hire's full monthly cost (wages plus employer costs), if known.
    burden_rate is the employer cost on top of wages (payroll taxes, insurance, benefits).
    """
    complete = _complete_months(books)
    if not complete:
        return {"status": "insufficient_history", "message": "Needs at least one complete month of books."}
    basis = complete[-12:] if len(complete) >= 12 else complete[-3:]
    summaries = [monthly_summary(books, m) for m in basis]
    n = len(summaries)
    revenue = sum(s["revenue"] for s in summaries) / n
    expenses = sum(s["expenses"] for s in summaries) / n
    profit = revenue - expenses
    variable = sum(v for s in summaries for k, v in s["expenses_by_category"].items() if k.lower() in VARIABLE) / n
    margin = (revenue - variable) / revenue if revenue else 0.0  # kept from each extra dollar of work

    jobs = pd.DataFrame(job_profitability(books)["jobs"])
    ticket = None
    if not jobs.empty:
        ends = books.jobs.set_index("job_id")["end_date"]
        jobs["month"] = jobs["job_id"].map(ends).dt.strftime("%Y-%m")
        recent = jobs[jobs["month"].isin(basis) & (jobs["quoted_revenue"] > 0)]
        if not recent.empty:
            ticket = recent["quoted_revenue"].sum() / len(recent)

    reserve = affordability(books, 1)  # a $1 check reads the cash and reserve figures
    spare = (reserve.get("available_cash") or 0) - (reserve.get("reserve_required") or 0)

    budget = max(0.0, profit)
    wages = budget / (1 + burden_rate)

    def needs(cost: float) -> dict:
        extra = cost / margin if margin > 0 else None
        return {
            "monthly_cost": round(cost, 2),
            "covered_by_current_profit": profit >= cost,
            "profit_after_hire": round(profit - cost, 2),
            "extra_revenue_to_keep_profit": round(extra, 2) if extra is not None else None,
            "growth_percent": round(extra / revenue * 100, 1) if extra is not None and revenue else None,
            "extra_jobs_per_month": round(extra / ticket, 1) if extra is not None and ticket else None,
            "months_spare_cash_covers": round(spare / cost, 1) if cost > 0 and spare > 0 else 0.0,
        }

    result = {
        "status": "evaluated",
        "basis": f"average of the last {n} complete months" + (" (a full year, so seasons even out)" if n == 12 else ""),
        "basis_months": basis,
        "average_monthly_revenue": round(revenue, 2),
        "average_monthly_expenses": round(expenses, 2),
        "average_monthly_profit": round(profit, 2),
        "margin_after_job_costs_percent": round(margin * 100, 1),
        "average_job_ticket": round(ticket, 2) if ticket else None,
        "spare_cash_above_reserve": round(spare, 2),
        "affordable_from_profit": {
            "monthly_cost": round(budget, 2),
            "monthly_wages": round(wages, 2),
            "hourly_full_time": round(wages / HOURS_PER_MONTH, 2),
            "yearly_salary": round(wages * 12, 2),
        },
        "extra_revenue_per_1000_of_monthly_cost": round(1000 / margin, 2) if margin > 0 else None,
        "assumptions": [f"Employer costs add {burden_rate:.0%} on top of wages (payroll taxes, insurance, benefits).",
                        "Full time is 40 hours a week.",
                        "Extra revenue keeps the margin left after materials, subcontractors, permits, fuel and "
                        "equipment rentals."],
    }
    if monthly_cost:
        result["proposed_hire"] = needs(monthly_cost)
    return result
