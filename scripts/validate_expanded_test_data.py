"""Validate fixture accounting through the real converter and finance functions.

Run: .venv/bin/python -m scripts.validate_expanded_test_data
Uses explicit column mappings and category hints; does not call AI or Plaid.
"""

import copy
import csv
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from backend.app.finance.cashflow import cash_balance, receivables
from backend.app.finance.expenses import monthly_summary
from backend.app.finance.report import build_report
from backend.app.integrations.ai import FileInterpretation
from backend.app.integrations.csv_import import _rows, convert, decode, parse_amount
from backend.app.integrations.records import ALL_CATEGORIES, BusinessFacts, Records, assemble

ROOT = Path(__file__).resolve().parents[1] / "test-data" / "expanded-finance"
FACTS = BusinessFacts(name="Cedar & Stone Property Services", labor_rate=52, tax_reserve_rate=0.25)
MONTHS = ["2026-05", "2026-06", "2026-07"]
COMMON = {"date": "Date", "description": "Description", "vendor": "Merchant", "category": "Category", "amount": "Amount"}
PLANS = {
    "business_checking.csv": {"kind": "transactions", "account": "bank", "amount_sign": "split_columns", "columns": {"date": "Posted Date", "description": "Description", "vendor": "Payee", "category": "Category", "debit": "Withdrawal", "credit": "Deposit", "balance": "Running Balance"}},
    "business_savings.csv": {"kind": "transactions", "account": "bank", "amount_sign": "direction_column", "outflow_values": ["DEBIT"], "columns": COMMON | {"direction": "Direction", "balance": "Balance"}},
    "business_credit_card.csv": {"kind": "transactions", "account": "credit_card", "amount_sign": "outflow_positive", "columns": COMMON | {"amount": "Charge Amount"}},
    "petty_cash.csv": {"kind": "transactions", "account": "bank", "columns": COMMON | {"balance": "Cash Balance"}},
    "customer_invoices.csv": {"kind": "invoices", "columns": {"invoice_id": "Invoice Number", "job_ref": "Work Order", "customer": "Customer", "issued": "Issued", "due": "Due", "invoice_total": "Invoice Total", "paid_amount": "Paid Amount", "paid_date": "Paid Date", "status": "Status"}},
    "jobs.csv": {"kind": "jobs", "columns": {"job_id": "Job ID", "customer": "Customer", "job_type": "Job Type", "start_date": "Start Date", "end_date": "End Date", "quoted_price": "Quoted Price", "labor_hours": "Labor Hours", "status": "Status"}},
}


def read(path, spec=None):
    spec = spec or PLANS.get(path.name) or {"kind": "transactions", "account": "accounting", "columns": COMMON}
    plan = FileInterpretation(source=f"Synthetic {path.name}", header_row=0, **spec)
    records = convert(_rows(decode(path.read_bytes()), 0), plan, path.name)
    for transaction in records.transactions:
        transaction.category = transaction.hint
    return records


def core(folder):
    records = Records()
    for filename in PLANS:
        records.extend(read(folder / filename))
    return records


def snapshot(records):
    books, warnings, summary = assemble(copy.deepcopy(records), FACTS)
    # Construct every month report, including job profit and expense comparisons.
    for month in MONTHS:
        assert build_report(books, month)["month"] == month
    return {
        "summary": summary,
        "monthly": [monthly_summary(books, month) for month in MONTHS],
        "cash_balance": cash_balance(books),
        "receivables": receivables(books),
        "job_status_counts": dict(Counter(books.jobs["status"])),
        "warnings": warnings,
    }


def check_running_balances():
    # Independent cent arithmetic over CSV rows checks balances, not converter output.
    closings = {}
    for folder in ("01-upload-together", "02-higher-cost-scenario"):
        total = Decimal(0)
        for filename, start, balance_column in (("business_checking.csv", 75000, "Running Balance"), ("business_savings.csv", 12000, "Balance"), ("petty_cash.csv", 300, "Cash Balance")):
            with (ROOT / folder / filename).open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            if filename == "business_checking.csv":
                rows.reverse()
            balance = Decimal(start)
            for row in rows:
                if filename == "business_checking.csv":
                    amount = Decimal(str(parse_amount(row["Deposit"]) or 0)) - Decimal(str(parse_amount(row["Withdrawal"]) or 0))
                else:
                    amount = Decimal(row["Amount"])
                    if row.get("Direction") == "DEBIT":
                        amount = -amount
                balance += amount
                assert balance == Decimal(row[balance_column]), (filename, row)
            total += balance
        closings[folder] = float(total)
    return closings


def main():
    baseline_records = core(ROOT / "01-upload-together")
    baseline = snapshot(baseline_records)
    higher = snapshot(core(ROOT / "02-higher-cost-scenario"))
    categories = {transaction.category for transaction in baseline_records.transactions}
    assert categories == set(ALL_CATEGORIES), categories
    assert baseline["summary"]["invoices"] == 15
    assert baseline["summary"]["jobs"] == 18
    assert baseline["summary"]["payment_dates_matched"] == 2
    assert baseline["receivables"]["total_outstanding"] == 34000
    assert baseline["job_status_counts"] == {"completed": 15, "quoted": 1, "in_progress": 1, "cancelled": 1}
    assert [month["revenue"] for month in baseline["monthly"]] == [21714, 25230, 22736]
    assert [month["expenses"] for month in baseline["monthly"]] == [26242.60, 22557.60, 24308.10]
    assert baseline["summary"]["transactions"] == 142
    assert baseline["summary"]["excluded_transactions"] == 25
    assert all(month["period_complete"] for month in baseline["monthly"])
    assert baseline["monthly"][2]["expenses"] + 3150 == higher["monthly"][2]["expenses"]
    closings = check_running_balances()
    assert baseline["cash_balance"]["balance"] == closings["01-upload-together"]
    assert higher["cash_balance"]["balance"] == closings["02-higher-cost-scenario"]
    assert baseline["cash_balance"]["balance"] - 1700 == higher["cash_balance"]["balance"]

    duplicate_records = copy.deepcopy(baseline_records)
    duplicate_records.extend(read(ROOT / "03-duplicate-check" / "overlapping_accounting_export.csv"))
    duplicates = snapshot(duplicate_records)
    assert duplicates["monthly"] == baseline["monthly"]
    assert duplicates["cash_balance"] == baseline["cash_balance"]
    assert duplicates["summary"] == baseline["summary"]
    assert any("Skipped 18 transactions" in warning for warning in duplicates["warnings"])
    # Same-source identical fuel purchases are both kept (six over three months).
    assert sum(t.description == "Diesel fuel crew truck" for t in baseline_records.transactions) == 6

    errors = ROOT / "04-error-checks"
    partial = read(errors / "partial_bad_rows.csv")
    books, warnings, summary = assemble(partial, BusinessFacts(name="Partial Row Test", opening_balance=45000))
    partial_month = monthly_summary(books, "2026-06")
    assert (partial_month["revenue"], partial_month["expenses"], partial_month["profit"]) == (500, 85.25, 414.75)
    assert summary["transactions"] == 2 and any("skipped 3 rows" in w for w in warnings)
    unreadable = read(errors / "unreadable_dates_and_amounts.csv")
    assert not unreadable.transactions and any("skipped 3 rows" in w for w in unreadable.warnings)
    try:
        assemble(unreadable, FACTS)
    except ValueError as error:
        assert "No business transactions found" in str(error)
    else:
        raise AssertionError("An all-invalid file must not produce empty books")
    assert (errors / "empty.csv").stat().st_size == 0
    with (ROOT / "05-reference-only-do-not-upload-with-core" / "payroll_breakdown.csv").open(newline="") as handle:
        payroll = list(csv.DictReader(handle))
    deductions = ["Federal Withholding", "State Withholding", "Employee Social Security", "Employee Medicare"]
    for row in payroll:
        assert Decimal(row["Gross Wages"]) - sum(Decimal(row[c]) for c in deductions) == Decimal(row["Net Wages"])
    assert sum(Decimal(row["Net Wages"]) for row in payroll) == 3900
    assert sum(Decimal(row[c]) for row in payroll for c in deductions) == 1050

    result = {
        "company": FACTS.name,
        "validation": "Real CSV converter, books loader and finance functions; explicit mappings and supplied category hints; no AI, Plaid or authenticated browser calls.",
        "labor_rate": 52, "tax_reserve_rate": 0.25,
        "categories_covered": sorted(categories),
        "baseline": baseline, "higher_cost": higher,
        "duplicates": {"skipped": 18, "monthly_totals_unchanged": True, "warnings": duplicates["warnings"]},
        "partial_bad_rows": {"summary": partial_month, "warnings": warnings},
    }
    (ROOT / "expected-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"validated": True, "baseline_transactions": baseline["summary"]["transactions"], "excluded_transactions": baseline["summary"]["excluded_transactions"], "monthly": baseline["monthly"], "cash_balance": baseline["cash_balance"]["balance"], "unpaid_invoices": 34000, "scenario_july_expense_increase": 3150, "duplicates_skipped": 18}, indent=2))


if __name__ == "__main__":
    main()
