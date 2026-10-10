"""Print all finance tool results as strict JSON, without an API or model."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.data import load_books
from backend.app.finance import (
    affordability,
    cash_balance,
    expense_changes,
    job_profitability,
    losing_jobs,
    margin_by_job_type,
    monthly_summary,
    receivables,
    recurring_charges,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--books",
        type=Path,
        help="Directory containing the four books files; defaults to bundled sample",
    )
    parser.add_argument("--month", default="2026-09")
    parser.add_argument("--purchase", default="15000", help="Purchase price in USD")
    args = parser.parse_args()
    books = load_books(args.books)
    results = {
        "business": books.business,
        "monthly_summary": monthly_summary(books, args.month),
        "expense_changes": expense_changes(books, args.month),
        "recurring_charges": recurring_charges(books, args.month),
        "job_profitability": job_profitability(books, args.month),
        "losing_jobs": losing_jobs(books, args.month),
        "margin_by_job_type": margin_by_job_type(books, args.month),
        "cash_balance": cash_balance(books),
        "receivables": receivables(books),
        "affordability": affordability(books, args.purchase),
    }
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
