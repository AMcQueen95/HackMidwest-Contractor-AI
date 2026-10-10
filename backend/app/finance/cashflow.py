"""Snapshot cash, receivables aging, and an explicit purchase reserve policy."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from backend.app.data.loader import Books, cents, number
from ._common import dollars, opening_balance_cents, tax_reserve
from .expenses import monthly_summary


def cash_balance(books: Books) -> dict:
    inflow = sum(
        int(value) for value in books.transactions["_amount_cents"] if value > 0
    )
    outflow = -sum(
        int(value) for value in books.transactions["_amount_cents"] if value < 0
    )
    balance = opening_balance_cents(books) + inflow - outflow
    reserve = tax_reserve(books, inflow - outflow)
    return {
        "as_of_date": books.business["as_of_date"],
        "opening_balance_date": books.business["opening_balance_date"],
        "currency": "USD",
        "opening_balance": dollars(opening_balance_cents(books)),
        "cash_in": dollars(inflow),
        "cash_out": dollars(outflow),
        "balance": dollars(balance),
        "tax_reserve": dollars(reserve),
        "available_cash": dollars(balance - reserve),
    }


def receivables(books: Books) -> dict:
    as_of = date.fromisoformat(books.business["as_of_date"])
    aging = dict.fromkeys(["current", "1_30", "31_60", "61_90", "90_plus"], 0)
    invoices, customers = [], {}
    overdue = 0
    for _, row in books.invoices.sort_values(["due", "invoice_id"]).iterrows():
        amount = int(row["_amount_cents"] - row["_paid_amount_cents"])
        if amount <= 0:
            continue
        days = max(0, (as_of - row["due"].date()).days)
        bucket = (
            "current"
            if days == 0
            else "1_30"
            if days <= 30
            else "31_60"
            if days <= 60
            else "61_90"
            if days <= 90
            else "90_plus"
        )
        aging[bucket] += amount
        if days:
            overdue += amount
        customers[row["customer"]] = customers.get(row["customer"], 0) + amount
        invoices.append(
            {
                "invoice_id": row["invoice_id"],
                "job_id": row["job_id"],
                "customer": row["customer"],
                "due": row["due"].date().isoformat(),
                "outstanding": dollars(amount),
                "days_overdue": days,
                "aging_bucket": bucket,
            }
        )
    return {
        "as_of_date": as_of.isoformat(),
        "currency": "USD",
        "total_outstanding": dollars(sum(aging.values())),
        "overdue_total": dollars(overdue),
        "aging": {key: dollars(value) for key, value in aging.items()},
        "customers": [
            {"customer": key, "outstanding": dollars(value)}
            for key, value in sorted(
                customers.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "invoices": invoices,
    }


def affordability(
    books: Books, amount, reserve_months=1, reserve_month: str | None = None
) -> dict:
    purchase = cents(amount, "amount")
    months = number(reserve_months, "reserve_months")
    if purchase <= 0 or months < 0:
        raise ValueError(
            "amount must be positive and reserve_months must be nonnegative"
        )
    as_of = pd.Timestamp(books.business["as_of_date"])
    period = as_of.to_period("M")
    if as_of.date() != period.end_time.date():
        period -= 1
    reserve_month = str(period) if reserve_month is None else reserve_month
    summary = monthly_summary(books, reserve_month)
    expense_cents = cents(summary["expenses"], "expenses")
    cushion = int(
        (Decimal(expense_cents) * months).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    cash = cash_balance(books)
    balance = cents(cash["balance"], "balance")
    available = cents(cash["available_cash"], "available_cash")
    collections = cents(receivables(books)["total_outstanding"], "total_outstanding")
    profit = cents(cash["cash_in"], "cash_in") - cents(cash["cash_out"], "cash_out")
    projected_tax = tax_reserve(books, profit + collections)
    projected_available = balance + collections - projected_tax - purchase
    has_history = months == 0 or (
        summary["period_complete"]
        and summary["transaction_count"] > 0
        and expense_cents > 0
    )
    return {
        "as_of_date": books.business["as_of_date"],
        "currency": "USD",
        "purchase_amount": dollars(purchase),
        "reserve_month": reserve_month,
        "reserve_months": float(months),
        "reserve_required": dollars(cushion),
        "cash_balance": cash["balance"],
        "tax_reserve": cash["tax_reserve"],
        "available_cash": cash["available_cash"],
        "cash_after_purchase": dollars(balance - purchase),
        "available_after_purchase": dollars(available - purchase),
        "can_afford_now": available - purchase >= cushion if has_history else None,
        "shortfall": dollars(max(0, cushion - (available - purchase)))
        if has_history
        else None,
        "status": "evaluated" if has_history else "insufficient_expense_history",
        "collection_scenario": {
            "assumption": "All outstanding invoices are collected in full; no additional expenses occur. This is a scenario, not a forecast.",
            "collections": dollars(collections),
            "tax_reserve": dollars(projected_tax),
            "available_after_purchase": dollars(projected_available),
            "can_afford": projected_available >= cushion if has_history else None,
        },
    }
