"""Cash-basis summaries and expense comparisons, with no model arithmetic."""

import pandas as pd

from backend.app.data.loader import Books
from ._common import (
    dollars,
    expense_totals,
    month_window,
    percentage,
    transactions_for_month,
)


def monthly_summary(books: Books, month: str) -> dict:
    frame = transactions_for_month(books, month)
    start, end, complete = month_window(books, month)
    revenue = sum(int(value) for value in frame["_amount_cents"] if value > 0)
    expenses = -sum(int(value) for value in frame["_amount_cents"] if value < 0)
    return {
        "month": month,
        "basis": "cash",
        "currency": "USD",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "period_complete": complete,
        "revenue": dollars(revenue),
        "expenses": dollars(expenses),
        "profit": dollars(revenue - expenses),
        "transaction_count": len(frame),
        "expenses_by_category": {
            key: dollars(value) for key, value in sorted(expense_totals(frame).items())
        },
    }


def expense_changes(
    books: Books, month: str, previous_month: str | None = None
) -> dict:
    month_window(books, month)
    previous_month = (
        str(pd.Period(month, freq="M") - 1)
        if previous_month is None
        else previous_month
    )
    month_window(books, previous_month)
    if previous_month >= month:
        raise ValueError("previous_month must precede month")
    current = expense_totals(transactions_for_month(books, month))
    previous = expense_totals(transactions_for_month(books, previous_month))
    changes = []
    for category in sorted(current.keys() | previous.keys()):
        now, before = current.get(category, 0), previous.get(category, 0)
        changes.append(
            {
                "category": category,
                "previous": dollars(before),
                "current": dollars(now),
                "change": dollars(now - before),
                "change_percent": percentage(now - before, before),
            }
        )
    changes.sort(key=lambda row: (-row["change"], row["category"]))
    return {
        "month": month,
        "previous_month": previous_month,
        "basis": "cash",
        "currency": "USD",
        "period_complete": month_window(books, month)[2],
        "previous_period_complete": month_window(books, previous_month)[2],
        "changes": changes,
    }


def recurring_charges(books: Books, month: str | None = None) -> dict:
    month = month or books.business["as_of_date"][:7]
    _, end, _ = month_window(books, month)
    expenses = books.transactions.loc[
        (books.transactions["_amount_cents"] < 0)
        & (books.transactions["date"] <= pd.Timestamp(end))
    ].copy()
    expenses["_vendor"] = expenses["vendor"].str.casefold()
    expenses["_category"] = expenses["category"].str.casefold()
    expenses["_month"] = expenses["date"].dt.strftime("%Y-%m")
    charges = []
    for (_, category), group in expenses.groupby(["_vendor", "_category"], sort=True):
        totals = {
            key: -sum(int(value) for value in rows["_amount_cents"])
            for key, rows in group.groupby("_month", sort=True)
        }
        if len(totals) < 2 or month not in totals:
            continue
        charges.append(
            {
                "vendor": group.iloc[0]["vendor"],
                "category": category,
                "months": sorted(totals),
                "latest_monthly_amount": dollars(totals[month]),
                "average_monthly_amount": round(
                    sum(totals.values()) / len(totals) / 100, 2
                ),
            }
        )
    software = expenses.loc[
        (expenses["_month"] == month) & expenses["_category"].eq("software")
    ]
    vendors = sorted(software["vendor"].unique().tolist())
    potential = []
    if len(set(software["_vendor"])) > 1:
        potential.append(
            {
                "category": "software",
                "vendors": vendors,
                "monthly_total": dollars(
                    -sum(int(value) for value in software["_amount_cents"])
                ),
                "reason": "Multiple software vendors; review whether their services overlap. This is not proof of duplicate subscriptions.",
            }
        )
    return {
        "month": month,
        "currency": "USD",
        "charges": charges,
        "potential_duplicate_groups": potential,
    }
