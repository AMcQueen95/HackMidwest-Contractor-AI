import json

import pytest

from backend.app.data import load_books_from_uploads
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


def test_sample_months_and_cash_reconcile(books):
    august = monthly_summary(books, "2026-08")
    september = monthly_summary(books, "2026-09")
    assert (august["revenue"], august["expenses"], august["profit"]) == (
        60000,
        45000,
        15000,
    )
    assert (september["revenue"], september["expenses"], september["profit"]) == (
        45070,
        52900,
        -7830,
    )
    assert september["basis"] == "cash"
    assert sum(september["expenses_by_category"].values()) == september["expenses"]
    cash = cash_balance(books)
    assert cash["balance"] == 45000 + august["profit"] + september["profit"] == 52170
    assert cash["tax_reserve"] == 717
    assert cash["available_cash"] == 51453


def test_expense_increases_match_demo(books):
    changes = {
        row["category"]: row for row in expense_changes(books, "2026-09")["changes"]
    }
    assert changes["fuel"]["change_percent"] == 35
    assert changes["insurance"]["change_percent"] == 26
    assert changes["software"]["change_percent"] == 176.01
    assert changes["software"]["change"] == 361.57


def test_small_amounts_sum_exactly_in_cents(sample_files, change_csv):
    def change(rows):
        rows.clear()
        for amount in ["1.00", "-0.10", "-0.20"]:
            rows.append(
                {
                    "date": "2026-09-01",
                    "description": "Small transaction",
                    "vendor": "Shop",
                    "category": "test",
                    "amount": amount,
                    "job_id": "",
                }
            )

    files = change_csv(sample_files, "transactions.csv", change)
    report = monthly_summary(load_books_from_uploads(files), "2026-09")
    assert report["expenses"] == 0.30 and report["profit"] == 0.70


def test_new_expense_has_no_invented_percentage(sample_files, change_csv):
    files = change_csv(
        sample_files,
        "transactions.csv",
        lambda rows: rows.append(
            {
                "date": "2026-09-20",
                "description": "New equipment rental",
                "vendor": "Rental Shop",
                "category": "rental",
                "amount": "-500",
                "job_id": "",
            }
        ),
    )
    report = expense_changes(load_books_from_uploads(files), "2026-09")
    rental = next(row for row in report["changes"] if row["category"] == "rental")
    assert rental["previous"] == 0 and rental["change"] == 500
    assert rental["change_percent"] is None


def test_recurring_bills_and_possible_overlap(books):
    report = recurring_charges(books, "2026-09")
    housecall = next(
        row for row in report["charges"] if row["vendor"] == "Housecall Pro"
    )
    payroll = next(
        row for row in report["charges"] if row["vendor"] == "Ridgeline Payroll"
    )
    assert housecall["months"] == ["2026-08", "2026-09"]
    assert housecall["latest_monthly_amount"] == 169
    assert payroll["latest_monthly_amount"] == 26000  # two pay runs, one monthly total
    candidate = report["potential_duplicate_groups"][0]
    assert candidate["vendors"] == ["Housecall Pro", "ServiceTitan"]
    assert candidate["monthly_total"] == 567
    assert "not proof" in candidate["reason"]


def test_losing_job_and_quote_vs_cash_distinction(books):
    report = losing_jobs(books, "2026-09")
    assert report["revenue_basis"] == "quoted_price"
    assert len(report["jobs"]) == 1
    westport = report["jobs"][0]
    assert westport["job_id"] == "SEP-001"
    assert westport["quoted_revenue"] == 12000 and westport["cash_received"] == 0
    assert westport["direct_expenses"] == 9232 and westport["labor_cost"] == 4000
    assert westport["profit"] == -1232


def test_posted_labor_replaces_estimate(sample_files, change_csv):
    files = change_csv(
        sample_files,
        "transactions.csv",
        lambda rows: rows.append(
            {
                "date": "2026-09-15",
                "description": "Allocated labor",
                "vendor": "Payroll",
                "category": "labor",
                "amount": "-3000",
                "job_id": "SEP-001",
            }
        ),
    )
    report = job_profitability(load_books_from_uploads(files), "2026-09")
    westport = next(row for row in report["jobs"] if row["job_id"] == "SEP-001")
    assert westport["labor_cost_source"] == "posted"
    assert westport["total_cost"] == 12232 and westport["profit"] == -232


def test_job_type_margin_uses_totals_not_average_percentages(books):
    plumbing = next(
        row
        for row in margin_by_job_type(books, "2026-09")["job_types"]
        if row["job_type"] == "plumbing"
    )
    assert plumbing["job_count"] == 2
    assert plumbing["quoted_revenue"] == 24070
    assert plumbing["profit"] == 12902
    assert plumbing["margin_percent"] == 53.6


def test_zero_quote_has_null_margin(sample_files, change_csv):
    files = change_csv(
        sample_files, "jobs.csv", lambda rows: rows[3].update(quoted_price="0")
    )
    westport = next(
        row
        for row in job_profitability(load_books_from_uploads(files))["jobs"]
        if row["job_id"] == "SEP-001"
    )
    assert westport["margin_percent"] is None
    assert westport["profit"] == -13232


def test_fractional_labor_rounds_half_cent_up(sample_files, change_csv):
    files = change_csv(
        sample_files, "jobs.csv", lambda rows: rows[3].update(labor_hours="0.0001")
    )
    westport = next(
        row
        for row in job_profitability(load_books_from_uploads(files))["jobs"]
        if row["job_id"] == "SEP-001"
    )
    assert westport["labor_cost"] == 0.01


def test_in_progress_jobs_are_not_reported_as_finished_margins(
    sample_files, change_csv
):
    files = change_csv(
        sample_files,
        "jobs.csv",
        lambda rows: rows[3].update(status="in_progress", end_date=""),
    )
    assert "SEP-001" not in [
        row["job_id"]
        for row in job_profitability(load_books_from_uploads(files))["jobs"]
    ]


def test_receivables_snapshot_and_partial_payments(books, sample_files, change_csv):
    report = receivables(books)
    assert report["total_outstanding"] == report["overdue_total"] == 21000
    assert report["aging"]["1_30"] == 21000
    assert [row["days_overdue"] for row in report["invoices"]] == [10, 5]
    files = change_csv(
        sample_files,
        "invoices.csv",
        lambda rows: rows[3].update(paid_amount="4000", paid_date="2026-09-20"),
    )
    partial = receivables(load_books_from_uploads(files))
    assert partial["total_outstanding"] == 17000
    assert partial["invoices"][0]["outstanding"] == 8000


def test_receivables_aging_boundaries(sample_files, change_csv):
    def change(rows):
        rows[3].update(issued="2026-08-01", due="2026-08-16")
        rows[4].update(due="2026-09-30")

    files = change_csv(sample_files, "invoices.csv", change)
    aging = receivables(load_books_from_uploads(files))["aging"]
    assert aging["31_60"] == 12000 and aging["current"] == 9000


def test_purchase_policy_and_collection_scenario(books):
    report = affordability(books, 15000)
    assert report["can_afford_now"] is False
    assert report["reserve_required"] == 52900
    assert report["shortfall"] == 16447
    scenario = report["collection_scenario"]
    assert scenario["can_afford"] is True
    assert scenario["tax_reserve"] == 2817
    assert scenario["available_after_purchase"] == 55353
    assert "not a forecast" in scenario["assumption"]
    assert affordability(books, 15000, reserve_months=0)["can_afford_now"] is True


def test_midmonth_uses_last_complete_month_for_reserve(sample_files):
    settings = json.loads(sample_files["business.json"])
    settings["as_of_date"] = "2026-10-15"
    books = load_books_from_uploads(
        sample_files | {"business.json": json.dumps(settings)}
    )
    assert affordability(books, 15000)["reserve_month"] == "2026-09"
    assert monthly_summary(books, "2026-10")["period_complete"] is False


def test_empty_books_do_not_claim_purchase_is_safe(sample_files, change_csv):
    for filename in ["transactions.csv", "jobs.csv", "invoices.csv"]:
        sample_files = change_csv(sample_files, filename, lambda rows: rows.clear())
    books = load_books_from_uploads(sample_files)
    assert monthly_summary(books, "2026-09")["profit"] == 0
    assert job_profitability(books)["jobs"] == []
    assert receivables(books)["total_outstanding"] == 0
    assert recurring_charges(books)["charges"] == []
    assert affordability(books, 15000)["can_afford_now"] is None


@pytest.mark.parametrize("month", ["2026", "2026-13", "2026-9", "2026-10", "garbage"])
def test_invalid_or_future_reporting_month_is_rejected(books, month):
    with pytest.raises(ValueError):
        monthly_summary(books, month)


@pytest.mark.parametrize(
    "amount,reserve_months", [(0, 1), (-10, 1), ("NaN", 1), ("15.001", 1), (15000, -1)]
)
def test_invalid_purchase_policy_is_rejected(books, amount, reserve_months):
    with pytest.raises(ValueError):
        affordability(books, amount, reserve_months)


def test_comparison_month_must_be_valid_and_earlier(books):
    for previous in ["2026-09", "2026-10", "bad", ""]:
        with pytest.raises(ValueError):
            expense_changes(books, "2026-09", previous)


def test_all_outputs_are_strict_json_and_do_not_mutate_books(books):
    before = [
        frame.copy(deep=True)
        for frame in (books.transactions, books.jobs, books.invoices)
    ]
    outputs = [
        monthly_summary(books, "2026-09"),
        expense_changes(books, "2026-09"),
        recurring_charges(books),
        job_profitability(books),
        losing_jobs(books),
        margin_by_job_type(books),
        cash_balance(books),
        receivables(books),
        affordability(books, "15000"),
    ]
    json.dumps(outputs, allow_nan=False)
    assert all(
        left.equals(right)
        for left, right in zip(before, (books.transactions, books.jobs, books.invoices))
    )
