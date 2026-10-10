"""Completed-job margins: quoted revenue, direct costs, and one labor source."""

import pandas as pd

from backend.app.data.loader import Books, cents
from ._common import dollars, month_window, percentage


def job_profitability(books: Books, month: str | None = None) -> dict:
    selected = books.jobs.loc[books.jobs["status"].eq("completed")]
    if month is not None:
        start, end, _ = month_window(books, month)
        selected = selected.loc[
            selected["end_date"].between(pd.Timestamp(start), pd.Timestamp(end))
        ]
    results = []
    for _, job in selected.sort_values("job_id").iterrows():
        ledger = books.transactions.loc[books.transactions["job_id"].eq(job["job_id"])]
        expenses = ledger.loc[ledger["_amount_cents"] < 0]
        labor_rows = expenses["category"].str.casefold().isin(["payroll", "labor"])
        direct = -sum(
            int(value) for value in expenses.loc[~labor_rows, "_amount_cents"]
        )
        posted_labor = -sum(
            int(value) for value in expenses.loc[labor_rows, "_amount_cents"]
        )
        labor = posted_labor if labor_rows.any() else int(job["_estimated_labor_cents"])
        revenue = int(job["_quoted_price_cents"])
        cost = direct + labor
        results.append(
            {
                "job_id": job["job_id"],
                "customer": job["customer"],
                "job_type": job["job_type"],
                "quoted_revenue": dollars(revenue),
                "cash_received": dollars(
                    sum(int(value) for value in ledger["_amount_cents"] if value > 0)
                ),
                "direct_expenses": dollars(direct),
                "labor_cost": dollars(labor),
                "labor_cost_source": "posted"
                if labor_rows.any()
                else "hours_times_rate",
                "total_cost": dollars(cost),
                "profit": dollars(revenue - cost),
                "margin_percent": percentage(revenue - cost, revenue),
                "cost_history_complete": job["start_date"].date().isoformat()
                >= books.business["opening_balance_date"],
            }
        )
    return {
        "month": month,
        "as_of_date": books.business["as_of_date"],
        "currency": "USD",
        "revenue_basis": "quoted_price",
        "excludes_unallocated_overhead": True,
        "jobs": results,
    }


def losing_jobs(books: Books, month: str | None = None) -> dict:
    result = job_profitability(books, month)
    result["jobs"] = sorted(
        (job for job in result["jobs"] if job["profit"] < 0),
        key=lambda job: (job["profit"], job["job_id"]),
    )
    return result


def margin_by_job_type(books: Books, month: str | None = None) -> dict:
    report = job_profitability(books, month)
    groups = {}
    # Sum cents derived from report fields; never average per-job percentages.
    for job in report["jobs"]:
        group = groups.setdefault(
            job["job_type"], {"job_count": 0, "revenue": 0, "cost": 0}
        )
        group["job_count"] += 1
        group["revenue"] += cents(job["quoted_revenue"], "quoted_revenue")
        group["cost"] += cents(job["total_cost"], "total_cost")
    rows = [
        {
            "job_type": name,
            "job_count": group["job_count"],
            "quoted_revenue": dollars(group["revenue"]),
            "total_cost": dollars(group["cost"]),
            "profit": dollars(group["revenue"] - group["cost"]),
            "margin_percent": percentage(
                group["revenue"] - group["cost"], group["revenue"]
            ),
        }
        for name, group in sorted(groups.items())
    ]
    return {key: value for key, value in report.items() if key != "jobs"} | {
        "job_types": rows
    }
