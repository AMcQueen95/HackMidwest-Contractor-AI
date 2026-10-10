"""Load and validate a complete, cash-basis snapshot before replacing any books."""

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Mapping

import pandas as pd

SAMPLE_DIRECTORY = Path(__file__).parent / "sample"
MAX_FILE_BYTES = 10 * 1024 * 1024
COLUMNS = {
    "transactions.csv": (
        "date",
        "description",
        "vendor",
        "category",
        "amount",
        "job_id",
    ),
    "jobs.csv": (
        "job_id",
        "customer",
        "job_type",
        "start_date",
        "end_date",
        "quoted_price",
        "labor_hours",
        "status",
    ),
    "invoices.csv": (
        "invoice_id",
        "job_id",
        "customer",
        "issued",
        "due",
        "amount",
        "paid_amount",
        "paid_date",
    ),
}


class BooksValidationError(ValueError):
    """An input file violates the documented books contract."""


@dataclass(frozen=True)
class Books:
    transactions: pd.DataFrame
    jobs: pd.DataFrame
    invoices: pd.DataFrame
    business: dict


def number(value, field: str) -> Decimal:
    """Parse finite decimal input without accepting booleans or NaN."""
    try:
        if isinstance(value, bool):
            raise InvalidOperation
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) > Decimal("1000000000000"):
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError):
        raise BooksValidationError(
            f"{field}: expected a finite number of reasonable size"
        ) from None


def cents(value, field: str) -> int:
    result = number(value, field) * 100
    if result != result.to_integral_value():
        raise BooksValidationError(
            f"{field}: monetary amounts must have at most two decimal places"
        )
    return int(result)


def parse_date(value, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise BooksValidationError(f"{field}: expected an ISO date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BooksValidationError(f"{field}: invalid calendar date") from None


def _text(content: bytes | str, filename: str) -> str:
    if not isinstance(content, (bytes, str)):
        raise BooksValidationError(f"{filename}: expected bytes or text")
    if (
        len(content if isinstance(content, bytes) else content.encode("utf-8"))
        > MAX_FILE_BYTES
    ):
        raise BooksValidationError(f"{filename}: exceeds the 10 MiB size limit")
    try:
        return (
            content.decode("utf-8-sig")
            if isinstance(content, bytes)
            else content.lstrip("\ufeff")
        )
    except UnicodeDecodeError:
        raise BooksValidationError(f"{filename}: expected UTF-8 text") from None


def _csv(content: bytes | str, filename: str) -> pd.DataFrame:
    text = _text(content, filename)
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error:
        raise BooksValidationError(f"{filename}: malformed CSV") from None
    if not rows:
        raise BooksValidationError(f"{filename}: missing CSV header")
    header = rows[0]
    missing = sorted(set(COLUMNS[filename]) - set(header))
    if missing:
        raise BooksValidationError(f"{filename}: missing columns: {', '.join(missing)}")
    if len(header) != len(set(header)):
        raise BooksValidationError(f"{filename}: duplicate column names")
    if any(len(row) != len(header) for row in rows[1:]):
        raise BooksValidationError(
            f"{filename}: rows must match the header's column count"
        )
    # Select declared columns so uploads cannot inject internal calculation columns.
    return pd.DataFrame(rows[1:], columns=header)[list(COLUMNS[filename])].map(
        str.strip
    )


def _required(frame: pd.DataFrame, columns: tuple[str, ...], filename: str):
    for column in columns:
        if frame[column].eq("").any():
            raise BooksValidationError(
                f"{filename}.{column}: empty values are not allowed"
            )


def _dates(frame: pd.DataFrame, column: str, filename: str, optional=False):
    parsed = [
        None if optional and value == "" else parse_date(value, f"{filename}.{column}")
        for value in frame[column]
    ]
    try:
        frame[column] = pd.to_datetime(
            pd.Series(parsed, index=frame.index), errors="raise"
        )
    except (ValueError, OverflowError):
        raise BooksValidationError(
            f"{filename}.{column}: date is outside the supported range"
        ) from None


def _money(frame: pd.DataFrame, column: str, filename: str, nonnegative=False):
    amounts = [cents(value, f"{filename}.{column}") for value in frame[column]]
    if nonnegative and any(value < 0 for value in amounts):
        raise BooksValidationError(
            f"{filename}.{column}: negative amounts are not allowed"
        )
    frame[f"_{column}_cents"] = pd.Series(amounts, index=frame.index, dtype=object)
    frame[column] = [value / 100 for value in amounts]


def _business(content: bytes | str) -> dict:
    try:
        data = json.loads(_text(content, "business.json"), parse_float=Decimal)
    except (json.JSONDecodeError, RecursionError):
        raise BooksValidationError("business.json: malformed JSON") from None
    required = {
        "name",
        "opening_balance",
        "opening_balance_date",
        "as_of_date",
        "labor_rate",
        "tax_reserve_rate",
        "accounting_basis",
        "currency",
    }
    if not isinstance(data, dict) or required - data.keys():
        raise BooksValidationError("business.json: missing required business fields")
    if not isinstance(data["name"], str) or not data["name"].strip():
        raise BooksValidationError("business.json.name: expected a nonempty name")
    if data["accounting_basis"] != "cash" or data["currency"] != "USD":
        raise BooksValidationError(
            "business.json: this version supports cash-basis USD books only"
        )
    opening = parse_date(
        data["opening_balance_date"], "business.json.opening_balance_date"
    )
    as_of = parse_date(data["as_of_date"], "business.json.as_of_date")
    if opening > as_of:
        raise BooksValidationError(
            "business.json: opening balance date must not follow as-of date"
        )
    labor = cents(data["labor_rate"], "business.json.labor_rate")
    tax = number(data["tax_reserve_rate"], "business.json.tax_reserve_rate")
    if labor < 0 or not 0 <= tax <= 1:
        raise BooksValidationError(
            "business.json: labor rate must be nonnegative; tax reserve rate must be between 0 and 1"
        )
    return {
        "name": data["name"].strip(),
        "currency": "USD",
        "accounting_basis": "cash",
        "opening_balance_date": opening.isoformat(),
        "as_of_date": as_of.isoformat(),
        "opening_balance": cents(
            data["opening_balance"], "business.json.opening_balance"
        )
        / 100,
        "labor_rate": labor / 100,
        "tax_reserve_rate": float(tax),
    }


def load_books_from_uploads(files: Mapping[str, bytes | str]) -> Books:
    """Validate all four named files atomically; never mutate a current dataset."""
    missing = sorted((set(COLUMNS) | {"business.json"}) - files.keys())
    if missing:
        raise BooksValidationError(f"Missing files: {', '.join(missing)}")
    business = _business(files["business.json"])
    tx, jobs, invoices = (_csv(files[name], name) for name in COLUMNS)
    _required(
        tx, ("date", "description", "vendor", "category", "amount"), "transactions.csv"
    )
    _required(
        jobs,
        (
            "job_id",
            "customer",
            "job_type",
            "start_date",
            "quoted_price",
            "labor_hours",
            "status",
        ),
        "jobs.csv",
    )
    _required(
        invoices,
        ("invoice_id", "job_id", "customer", "issued", "due", "amount", "paid_amount"),
        "invoices.csv",
    )
    for frame, column, name in [
        (jobs, "job_id", "jobs.csv"),
        (invoices, "invoice_id", "invoices.csv"),
    ]:
        if frame[column].duplicated().any():
            raise BooksValidationError(f"{name}.{column}: duplicate IDs")
    ids = set(jobs["job_id"])
    if set(tx.loc[tx["job_id"] != "", "job_id"]) - ids or set(invoices["job_id"]) - ids:
        raise BooksValidationError("transactions.csv or invoices.csv: unknown job_id")
    customers = jobs.set_index("job_id")["customer"].to_dict()
    if any(row.customer != customers[row.job_id] for row in invoices.itertuples()):
        raise BooksValidationError("invoices.csv.customer: must match the linked job")

    _dates(tx, "date", "transactions.csv")
    for column in ("start_date", "end_date"):
        _dates(jobs, column, "jobs.csv", optional=column == "end_date")
    for column in ("issued", "due", "paid_date"):
        _dates(invoices, column, "invoices.csv", optional=column == "paid_date")
    for frame, column, name, nonnegative in [
        (tx, "amount", "transactions.csv", False),
        (jobs, "quoted_price", "jobs.csv", True),
        (invoices, "amount", "invoices.csv", True),
        (invoices, "paid_amount", "invoices.csv", True),
    ]:
        _money(frame, column, name, nonnegative)
    hours = [number(value, "jobs.csv.labor_hours") for value in jobs["labor_hours"]]
    if any(value < 0 for value in hours):
        raise BooksValidationError(
            "jobs.csv.labor_hours: negative hours are not allowed"
        )
    jobs["labor_hours"] = [float(value) for value in hours]
    labor_rate = cents(business["labor_rate"], "labor_rate")
    jobs["_estimated_labor_cents"] = pd.Series(
        [
            int((value * labor_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            for value in hours
        ],
        index=jobs.index,
        dtype=object,
    )
    if (
        not jobs["status"]
        .isin(["completed", "in_progress", "quoted", "cancelled"])
        .all()
    ):
        raise BooksValidationError(
            "jobs.csv.status: expected completed, in_progress, quoted, or cancelled"
        )
    if (jobs["status"].eq("completed") & jobs["end_date"].isna()).any() or (
        jobs["end_date"] < jobs["start_date"]
    ).any():
        raise BooksValidationError(
            "jobs.csv: completed jobs need an end date; end must not precede start"
        )
    as_of = pd.Timestamp(business["as_of_date"])
    opening = pd.Timestamp(business["opening_balance_date"])
    if ((tx["date"] < opening) | (tx["date"] > as_of)).any():
        raise BooksValidationError(
            "transactions.csv.date: must be within the opening-balance/as-of window"
        )
    for frame, column, filename in [
        (jobs, "start_date", "jobs.csv"),
        (jobs, "end_date", "jobs.csv"),
        (invoices, "issued", "invoices.csv"),
        (invoices, "paid_date", "invoices.csv"),
    ]:
        if (frame[column] > as_of).any():
            raise BooksValidationError(
                f"{filename}.{column}: cannot follow the snapshot's as-of date"
            )
    if (invoices["due"] < invoices["issued"]).any():
        raise BooksValidationError("invoices.csv.due: must not precede issue date")
    if (invoices["_paid_amount_cents"] > invoices["_amount_cents"]).any():
        raise BooksValidationError(
            "invoices.csv.paid_amount: cannot exceed invoice amount"
        )
    paid = invoices["_paid_amount_cents"] > 0
    if (
        (paid & invoices["paid_date"].isna()).any()
        or (~paid & invoices["paid_date"].notna()).any()
        or (invoices["paid_date"] < invoices["issued"]).any()
    ):
        raise BooksValidationError(
            "invoices.csv.paid_date: payments need a date on or after issue; unpaid invoices must leave it blank"
        )
    return Books(tx, jobs, invoices, business)


def load_books(directory: str | Path | None = None) -> Books:
    """Load the bundled sample by default, or a directory containing four books files."""
    directory = Path(directory) if directory is not None else SAMPLE_DIRECTORY
    files = {}
    for name in (*COLUMNS, "business.json"):
        try:
            if (directory / name).stat().st_size > MAX_FILE_BYTES:
                raise BooksValidationError(f"{name}: exceeds the 10 MiB size limit")
            files[name] = (directory / name).read_bytes()
        except OSError:
            raise BooksValidationError(
                f"Cannot read {name} in the books directory"
            ) from None
    return load_books_from_uploads(files)
