"""Read any CSV export, let the identify agent describe it, then convert it in code."""

import csv
import io
import re
from datetime import date

import pandas as pd

from backend.app.integrations.ai import FileInterpretation, identify
from backend.app.integrations.records import Invoice, Job, Records, Transaction

SAMPLE_LINES = 25


def decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Couldn't read the file as text")


def _rows(text: str, header_row: int) -> list[dict]:
    lines = text.splitlines()[header_row:]
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(lines, dialect)
    header = [h.strip() for h in next(reader, [])]
    rows = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue
        rows.append({h: (values[i].strip() if i < len(values) else "") for i, h in enumerate(header) if h})
    return rows


def parse_amount(value: str) -> float | None:
    """'$1,234.56', '(1,234.56)', '1234.56-', '-$12', '12.00 CR' -> float. Blank -> None."""
    s = (value or "").strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")") or s.endswith("-") or s.startswith("-") \
        or s.upper().endswith(" DR")
    s = re.sub(r"[^\d.]", "", s.upper().replace(" CR", "").replace(" DR", ""))
    if not s or s.count(".") > 1:
        return None
    number = float(s)
    return -number if negative else number


def parse_date(value: str, day_first: bool) -> date | None:
    if not (value or "").strip():
        return None
    parsed = pd.to_datetime(value.strip(), errors="coerce", dayfirst=day_first)
    return None if pd.isna(parsed) else parsed.date()


def _signed_amount(row: dict, plan: FileInterpretation) -> float | None:
    c = plan.columns
    if plan.amount_sign == "split_columns" or (c.debit and c.credit and not c.amount):
        out, inn = parse_amount(row.get(c.debit or "", "")), parse_amount(row.get(c.credit or "", ""))
        if out is None and inn is None:
            return None
        return abs(inn or 0) - abs(out or 0)
    value = parse_amount(row.get(c.amount or "", ""))
    if value is None:
        return None
    if plan.amount_sign == "outflow_positive":
        return -value
    if plan.amount_sign == "direction_column":
        direction = row.get(c.direction or "", "").strip().lower()
        is_out = direction in {v.strip().lower() for v in plan.outflow_values}
        return -abs(value) if is_out else abs(value)
    return value


def _status(value: str, has_end: bool) -> str:
    v = (value or "").lower()
    if "cancel" in v or "void" in v:
        return "cancelled"
    if any(w in v for w in ("quote", "estimate", "draft", "proposal")):
        return "quoted"
    if any(w in v for w in ("progress", "active", "scheduled", "open", "started", "upcoming")):
        return "in_progress"
    if any(w in v for w in ("complete", "done", "closed", "paid", "invoiced", "finished")):
        return "completed"
    return "completed" if has_end else "in_progress"


def convert(rows: list[dict], plan: FileInterpretation, source: str) -> Records:
    """Convert rows to records using the agent's description of the file."""
    c, out, skipped = plan.columns, Records(), 0
    header = set(rows[0]) if rows else set()
    for name, column in c.model_dump().items():  # never trust a column the file doesn't have
        if column and column not in header:
            setattr(c, name, None)
            out.warnings.append(f"{source}: expected a '{column}' column for {name}, but it isn't there.")

    if plan.kind == "transactions":
        for row in rows:
            day, amount = parse_date(row.get(c.date or "", ""), plan.day_first), _signed_amount(row, plan)
            if day is None or amount is None or amount == 0:
                skipped += 1
                continue
            desc = row.get(c.description or "", "") or row.get(c.vendor or "", "") or "Transaction"
            out.transactions.append(Transaction(
                date=day, description=desc, amount=round(amount, 2), vendor=row.get(c.vendor or "", ""),
                hint=row.get(c.category or "", ""), source=source,
                account=plan.account if plan.account != "other" else "bank",
                balance=parse_amount(row.get(c.balance or "", "")) if c.balance else None))
        if c.balance and plan.account == "bank" and out.transactions:
            # Bank exports may list newest first. Within a day, file order is the bank's order.
            newest_first = out.transactions[0].date > out.transactions[-1].date
            first_day = min(t.date for t in out.transactions)
            last_day = max(t.date for t in out.transactions)
            starts = [t for t in out.transactions if t.date == first_day and t.balance is not None]
            ends = [t for t in out.transactions if t.date == last_day and t.balance is not None]
            if starts:
                earliest = starts[-1] if newest_first else starts[0]
                out.opening_balance = round(earliest.balance - earliest.amount, 2)
            if ends:
                out.closing_balance = (ends[0] if newest_first else ends[-1]).balance

    elif plan.kind == "invoices":
        for n, row in enumerate(rows, 1):
            issued = parse_date(row.get(c.issued or "", ""), plan.day_first)
            total = parse_amount(row.get(c.invoice_total or "", ""))
            if issued is None or total is None:
                skipped += 1
                continue
            total = abs(total)
            if c.paid_amount:
                paid = abs(parse_amount(row.get(c.paid_amount, "")) or 0)
            elif c.open_balance:
                paid = total - abs(parse_amount(row.get(c.open_balance, "")) or 0)
            else:
                paid = total if "paid" in row.get(c.status or "", "").lower() else 0.0
            out.invoices.append(Invoice(
                invoice_id=row.get(c.invoice_id or "", "") or f"INV-{n:04d}",
                customer=row.get(c.customer or "", "") or "Unknown customer", issued=issued,
                due=parse_date(row.get(c.due or "", ""), plan.day_first) or issued,
                amount=total, paid_amount=max(0.0, min(paid, total)),
                paid_date=parse_date(row.get(c.paid_date or "", ""), plan.day_first),
                job_ref=row.get(c.job_ref or "", ""), source=source))

    elif plan.kind == "jobs":
        for n, row in enumerate(rows, 1):
            start = parse_date(row.get(c.start_date or "", ""), plan.day_first)
            end = parse_date(row.get(c.end_date or "", ""), plan.day_first)
            price = parse_amount(row.get(c.quoted_price or "", ""))
            if (start or end) is None or price is None:
                skipped += 1
                continue
            status = _status(row.get(c.status or "", ""), end is not None)
            out.jobs.append(Job(
                job_id=row.get(c.job_id or "", "") or f"JOB-{n:04d}",
                customer=row.get(c.customer or "", "") or "Unknown customer",
                job_type=row.get(c.job_type or "", "") or "unspecified",
                start_date=start or end, end_date=end or (start if status == "completed" else None),
                quoted_price=abs(price), labor_hours=abs(parse_amount(row.get(c.labor_hours or "", "")) or 0),
                status=status, source=source))

    if skipped:
        out.warnings.append(f"{source}: skipped {skipped} rows without a readable date or amount.")
    return out


async def read_file(filename: str, content: bytes) -> tuple[FileInterpretation, Records, int]:
    """Identify and convert one uploaded file. Returns the plan, records and row count."""
    text = decode(content)
    sample = [line for line in text.splitlines()[:SAMPLE_LINES]]
    if not any(line.strip() for line in sample):
        raise ValueError(f"{filename} is empty")
    plan = await identify(filename, sample)
    if plan.kind == "unknown":
        return plan, Records(warnings=[f"{filename}: not a transactions, invoices or jobs file, so it "
                                       f"was skipped. {plan.notes}".strip()]), 0
    rows = _rows(text, max(0, min(plan.header_row, len(sample) - 1)))
    return plan, convert(rows, plan, filename), len(rows)
