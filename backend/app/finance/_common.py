import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from backend.app.data.loader import Books, cents


def dollars(amount: int) -> float:
    return int(amount) / 100


def percentage(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def month_window(books: Books, month: str):
    if not isinstance(month, str) or not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("month must be YYYY-MM")
    try:
        period = pd.Period(month, freq="M")
        start, end = period.start_time.date(), period.end_time.date()
    except (ValueError, OverflowError):
        raise ValueError(
            "month must be a valid YYYY-MM within the supported date range"
        ) from None
    as_of = date.fromisoformat(books.business["as_of_date"])
    if start > as_of:
        raise ValueError("month cannot follow the books' as-of date")
    return (
        start,
        min(end, as_of),
        date.fromisoformat(books.business["opening_balance_date"]) <= start
        and as_of >= end,
    )


def transactions_for_month(books: Books, month: str):
    start, end, _ = month_window(books, month)
    return books.transactions.loc[
        books.transactions["date"].between(pd.Timestamp(start), pd.Timestamp(end))
    ]


def expense_totals(frame) -> dict[str, int]:
    totals = {}
    for category, amount in frame.loc[
        frame["_amount_cents"] < 0, ["category", "_amount_cents"]
    ].itertuples(index=False, name=None):
        category = category.casefold()
        totals[category] = totals.get(category, 0) - int(amount)
    return totals


def tax_reserve(books: Books, profit_cents: int) -> int:
    return int(
        (
            Decimal(max(0, profit_cents))
            * Decimal(str(books.business["tax_reserve_rate"]))
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def opening_balance_cents(books: Books) -> int:
    return cents(books.business["opening_balance"], "opening_balance")
