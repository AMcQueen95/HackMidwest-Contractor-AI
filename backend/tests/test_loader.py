import csv
import io
import json

import pytest

from backend.app.data import BooksValidationError, load_books, load_books_from_uploads


def test_default_sample_and_bytes_uploads_agree(sample_files):
    books = load_books()
    uploaded = load_books_from_uploads(
        {name: text.encode("utf-8") for name, text in sample_files.items()}
    )
    assert uploaded.business == books.business
    assert len(books.jobs) == 7
    assert len(books.transactions) == 28
    assert uploaded.transactions.equals(books.transactions)


@pytest.mark.parametrize(
    "filename,column,value,message",
    [
        ("transactions.csv", "date", "2026-09-31", "invalid calendar"),
        ("transactions.csv", "date", "2026-10-01", "as-of window"),
        ("transactions.csv", "date", "2026-07-31", "as-of window"),
        ("transactions.csv", "date", "09/01/2026", "ISO date"),
        ("transactions.csv", "amount", "12.345", "two decimal"),
        ("transactions.csv", "amount", "NaN", "finite number"),
        ("transactions.csv", "amount", "Infinity", "finite number"),
        ("transactions.csv", "amount", "dollars", "finite number"),
        ("transactions.csv", "vendor", "", "empty values"),
        ("transactions.csv", "job_id", "UNKNOWN", "unknown job_id"),
        ("jobs.csv", "quoted_price", "-1", "negative amounts"),
        ("jobs.csv", "labor_hours", "-1", "negative hours"),
        ("jobs.csv", "status", "unknown", "expected completed"),
        ("jobs.csv", "end_date", "", "need an end date"),
        ("jobs.csv", "end_date", "2026-07-30", "end must not precede"),
        ("invoices.csv", "job_id", "UNKNOWN", "unknown job_id"),
        ("invoices.csv", "customer", "Wrong customer", "must match"),
        ("invoices.csv", "paid_amount", "99999", "cannot exceed"),
        ("invoices.csv", "paid_amount", "-1", "negative amounts"),
        ("invoices.csv", "paid_date", "", "payments need a date"),
        ("invoices.csv", "paid_date", "2026-08-01", "on or after issue"),
        ("invoices.csv", "due", "2026-08-01", "must not precede"),
    ],
)
def test_invalid_cells_are_actionable(
    sample_files, change_csv, filename, column, value, message
):
    invalid = change_csv(
        sample_files, filename, lambda rows: rows[0].update({column: value})
    )
    with pytest.raises(BooksValidationError, match=message):
        load_books_from_uploads(invalid)


@pytest.mark.parametrize("filename", ["jobs.csv", "invoices.csv"])
def test_duplicate_ids_are_rejected(sample_files, change_csv, filename):
    invalid = change_csv(
        sample_files, filename, lambda rows: rows.append(rows[0].copy())
    )
    with pytest.raises(BooksValidationError, match="duplicate IDs"):
        load_books_from_uploads(invalid)


def test_unpaid_invoice_cannot_have_payment_date(sample_files, change_csv):
    invalid = change_csv(
        sample_files,
        "invoices.csv",
        lambda rows: rows[3].update(paid_date="2026-09-20"),
    )
    with pytest.raises(
        BooksValidationError, match="unpaid invoices must leave it blank"
    ):
        load_books_from_uploads(invalid)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("opening_balance_date", "2026-10-01", "must not follow"),
        ("tax_reserve_rate", 1.1, "between 0 and 1"),
        ("tax_reserve_rate", True, "finite number"),
        ("labor_rate", -10, "labor rate must be nonnegative"),
        ("accounting_basis", "accrual", "cash-basis USD"),
        ("currency", "EUR", "cash-basis USD"),
        ("name", "", "nonempty name"),
    ],
)
def test_invalid_business_settings(sample_files, field, value, message):
    business = json.loads(sample_files["business.json"])
    business[field] = value
    with pytest.raises(BooksValidationError, match=message):
        load_books_from_uploads(sample_files | {"business.json": json.dumps(business)})


def test_missing_file_and_unreadable_directory(sample_files, tmp_path):
    del sample_files["jobs.csv"]
    with pytest.raises(BooksValidationError, match="Missing files: jobs.csv"):
        load_books_from_uploads(sample_files)
    with pytest.raises(BooksValidationError, match="Cannot read transactions.csv"):
        load_books(tmp_path)


def test_malformed_headers_rows_encoding_and_json(sample_files):
    for name, text, message in [
        ("transactions.csv", "date,amount\n2026-09-01,10\n", "missing columns"),
        (
            "transactions.csv",
            sample_files["transactions.csv"].replace(
                "date,description", "date,date,description", 1
            ),
            "duplicate column",
        ),
        (
            "transactions.csv",
            sample_files["transactions.csv"] + "too,few,fields\n",
            "column count",
        ),
        ("transactions.csv", b"\xff", "UTF-8"),
        ("business.json", "not json", "malformed JSON"),
    ]:
        with pytest.raises(BooksValidationError, match=message):
            load_books_from_uploads(sample_files | {name: text})


def test_extra_columns_cannot_override_cents(sample_files):
    stream = io.StringIO()
    reader = csv.DictReader(io.StringIO(sample_files["transactions.csv"]))
    writer = csv.DictWriter(stream, fieldnames=reader.fieldnames + ["_amount_cents"])
    writer.writeheader()
    for row in reader:
        writer.writerow(row | {"_amount_cents": "99999999"})
    books = load_books_from_uploads(
        sample_files | {"transactions.csv": stream.getvalue()}
    )
    assert books.transactions.iloc[0]["_amount_cents"] == -100000


def test_empty_tables_with_headers_are_valid(sample_files, change_csv):
    for filename in ["transactions.csv", "jobs.csv", "invoices.csv"]:
        sample_files = change_csv(sample_files, filename, lambda rows: rows.clear())
    books = load_books_from_uploads(sample_files)
    assert books.transactions.empty and books.jobs.empty and books.invoices.empty


def test_failed_upload_preserves_existing_books(books, sample_files):
    before = books.transactions.copy(deep=True)
    with pytest.raises(BooksValidationError):
        load_books_from_uploads(sample_files | {"jobs.csv": "bad"})
    assert books.transactions.equals(before)
