"""Normalized records every source produces, and their assembly into validated books."""

import csv
import io
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from backend.app.data import Books, load_books_from_uploads
from backend.app.data.loader import COLUMNS

# Categories the finance functions and agents work with. Income is money in from
# customers; the excluded ones are moves of money that aren't business income or
# spending, so they stay out of profit.
CATEGORIES = {
    "income": "Payments from customers for work",
    "materials": "Parts, equipment and supplies for jobs (supply houses, hardware stores)",
    "payroll": "Wages, payroll services, payroll taxes",
    "subcontractors": "Payments to other contractors or crews",
    "fuel": "Gas and diesel for vehicles and equipment",
    "vehicle": "Truck payments, repairs, maintenance, tires, registration",
    "equipment": "Tools and equipment bought or rented",
    "insurance": "Business, liability, vehicle and workers' comp insurance",
    "rent": "Shop, office or yard rent",
    "utilities": "Electric, gas, water, phone, internet",
    "software": "Software and app subscriptions",
    "marketing": "Ads, lead services, signs, website",
    "permits": "Permits, licenses, inspection fees",
    "bank_fees": "Bank, card processing and loan interest charges",
    "taxes": "Tax payments to IRS or state",
    "overhead": "Other business costs: office supplies, meals, dues, professional services",
}
EXCLUDED = {
    "transfer": "Money moved between the business's own accounts, including credit card payments",
    "owner": "Owner draws, owner contributions, personal spending",
    "loan": "Loan proceeds or loan principal payments",
}
ALL_CATEGORIES = {**CATEGORIES, **EXCLUDED}


@dataclass
class Transaction:
    date: date
    description: str
    amount: float  # money in is positive, money out is negative
    vendor: str = ""
    category: str = ""  # one of ALL_CATEGORIES once categorized
    hint: str = ""  # the source's own category, if it has one
    source: str = ""
    account: str = "bank"  # bank, credit_card, accounting
    balance: float | None = None  # running balance after this row, if the source gives one


@dataclass
class Invoice:
    invoice_id: str
    customer: str
    issued: date
    due: date
    amount: float
    paid_amount: float = 0.0
    paid_date: date | None = None
    job_ref: str = ""
    source: str = ""


@dataclass
class Job:
    job_id: str
    customer: str
    job_type: str
    start_date: date
    end_date: date | None
    quoted_price: float
    labor_hours: float = 0.0
    status: str = "completed"
    source: str = ""


@dataclass
class Records:
    transactions: list[Transaction] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)
    opening_balance: float | None = None  # starting cash, when only that is known
    closing_balance: float | None = None  # what the bank accounts hold now, when known
    warnings: list[str] = field(default_factory=list)

    def extend(self, other: "Records") -> None:
        self.transactions += other.transactions
        self.invoices += other.invoices
        self.jobs += other.jobs
        self.warnings += other.warnings
        if other.opening_balance is not None:
            self.opening_balance = (self.opening_balance or 0.0) + other.opening_balance
        if other.closing_balance is not None:
            self.closing_balance = (self.closing_balance or 0.0) + other.closing_balance


@dataclass
class BusinessFacts:
    """What only the owner knows. Everything has a default so importing never blocks."""

    name: str = "My business"
    opening_balance: float | None = None
    labor_rate: float = 0.0
    tax_reserve_rate: float = 0.25


def _csv(rows: list[dict], columns: tuple[str, ...]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _money(value: float) -> str:
    return f"{round(value + 0.0, 2):.2f}"


def _dedupe(transactions: list[Transaction]) -> tuple[list[Transaction], int]:
    """The same payment can appear in two exports (bank and accounting). Keep the first."""
    seen, kept = {}, []
    for t in transactions:
        key = (t.date, round(t.amount, 2), t.description.lower()[:12])
        if key in seen and seen[key] != t.source:
            continue
        seen.setdefault(key, t.source)
        kept.append(t)
    return kept, len(transactions) - len(kept)


def _match_payment_dates(invoices: list[Invoice], transactions: list[Transaction]) -> int:
    """Fill missing payment dates from matching customer deposits. Returns how many matched."""
    deposits = sorted((t for t in transactions if t.category == "income"), key=lambda t: t.date)
    used, matched = set(), 0
    for inv in invoices:
        if inv.paid_amount <= 0 or inv.paid_date is not None:
            continue
        for i, t in enumerate(deposits):
            if i not in used and abs(t.amount - inv.paid_amount) < 0.01 \
                    and inv.issued <= t.date <= inv.issued + timedelta(days=180):
                inv.paid_date, matched = t.date, matched + 1
                used.add(i)
                break
    return matched


ESTIMATED = "(estimated from payment)"
# Payouts that bundle many customers (card processors) or say nothing about who paid.
_BATCHED = re.compile(r"stripe|square|paypal|venmo|shopify|clover|toast|payout|batch|deposit|transfer|"
                      r"atm|cash|branch|interest|dividend|refund|reversal", re.I)


def estimate_jobs(txs: list[Transaction], guess: Callable[[float, str], str] | None) -> tuple[list, list, int]:
    """Without a jobs export, treat each named customer payment as one finished, paid job.

    The job type is a guess from the payment size (by trade), labeled as estimated.
    Returns jobs, invoices and how many payments couldn't be tied to a customer.
    """
    jobs, invoices, batched = [], [], 0
    for n, t in enumerate(sorted((t for t in txs if t.category == "income"), key=lambda t: t.date), 1):
        customer = (t.vendor or "").strip()
        if not customer or _BATCHED.search(customer) or _BATCHED.search(t.description[:20]):
            batched += 1
            continue
        kind = guess(t.amount, customer) if guess else "Job"
        job = Job(job_id=f"EST-{n:04d}", customer=customer, job_type=f"{kind} {ESTIMATED}", start_date=t.date,
                  end_date=t.date, quoted_price=round(t.amount, 2), source="estimated")
        jobs.append(job)
        invoices.append(Invoice(invoice_id=f"EST-INV-{n:04d}", customer=customer, issued=t.date, due=t.date,
                                amount=round(t.amount, 2), paid_amount=round(t.amount, 2), paid_date=t.date,
                                job_ref=job.job_id, source="estimated"))
    return jobs, invoices, batched


def assemble(records: Records, facts: BusinessFacts,
             guess_job_type: Callable[[float, str], str] | None = None) -> tuple[Books, list[str], dict]:
    """Turn categorized records into books, validated by the loader.

    guess_job_type (from the owner's trade) names jobs estimated from payments when
    there's no jobs or invoices export. Returns the books, warnings for the owner,
    and a summary of what went in.
    """
    warnings = list(records.warnings)
    txs, dupes = _dedupe(records.transactions)
    if dupes:
        warnings.append(f"Skipped {dupes} transactions that appeared in more than one file.")

    excluded = [t for t in txs if t.category in EXCLUDED]
    txs = [t for t in txs if t.category in CATEGORIES]
    for name in EXCLUDED:
        hits = [t for t in excluded if t.category == name]
        if hits:
            warnings.append(f"Left out {len(hits)} {name} transactions (${sum(abs(t.amount) for t in hits):,.2f}) "
                            f"because they aren't business income or spending: {EXCLUDED[name].lower()}.")

    estimated = 0
    if not records.jobs and not records.invoices:
        est_jobs, est_invoices, batched = estimate_jobs(txs, guess_job_type)
        if est_jobs:
            records = Records(transactions=records.transactions, invoices=est_invoices, jobs=est_jobs,
                              opening_balance=records.opening_balance, closing_balance=records.closing_balance)
            estimated = len(est_jobs)
            warnings.append(
                f"No jobs export, so {estimated} jobs were estimated from customer payments. Their types are "
                f"guesses from the payment size, and job costs and margins need a jobs export from your "
                f"field-service app." + (f" {batched} payouts (card processors, deposits) bundle several "
                                         f"customers and count only as revenue." if batched else ""))

    # Jobs: every invoice needs a job. Exports without jobs get one job per invoice.
    jobs = {j.job_id: j for j in records.jobs}
    linked: set[str] = set()

    def same_customer_job(inv: Invoice) -> Job | None:
        """Accounting and field-service apps rarely share IDs: match on customer and price."""
        candidates = [j for j in records.jobs if j.job_id not in linked
                      and j.customer.strip().lower() == inv.customer.strip().lower()]
        exact = [j for j in candidates if abs(j.quoted_price - inv.amount) < 0.01]
        pool = exact or []
        return min(pool, key=lambda j: abs(((j.end_date or j.start_date) - inv.issued).days), default=None)

    invoices = []
    for inv in records.invoices:
        job = jobs.get(inv.job_ref) or jobs.get(inv.invoice_id) or same_customer_job(inv)
        if job is None:
            job = Job(job_id=inv.job_ref or f"JOB-{inv.invoice_id}", customer=inv.customer,
                      job_type="unspecified", start_date=inv.issued, end_date=inv.issued,
                      quoted_price=inv.amount, source=inv.source)
            jobs[job.job_id] = job
        if inv.customer != job.customer:
            inv.customer = job.customer
        inv.job_ref = job.job_id
        linked.add(job.job_id)
        invoices.append(inv)
    if any(j.job_type == "unspecified" for j in jobs.values()):
        warnings.append("Some invoices had no matching job, so each became its own job with the "
                        "invoice total as the price. Upload a jobs export for job types and hours.")

    matched = _match_payment_dates(invoices, txs)
    unmatched = [inv for inv in invoices if inv.paid_amount > 0 and inv.paid_date is None]
    for inv in unmatched:
        inv.paid_date = inv.issued
    if unmatched:
        warnings.append(f"{len(unmatched)} paid invoices had no payment date or matching deposit; "
                        f"their invoice date is used as the payment date.")

    dates = [t.date for t in txs]
    if not dates:
        raise ValueError("No business transactions found. Add a bank, card or accounting export, "
                         "or connect a bank account.")
    all_dates = dates + [d for inv in invoices for d in (inv.issued, inv.paid_date) if d] \
        + [d for j in jobs.values() for d in (j.start_date, j.end_date) if d]
    opening_date, as_of = min(dates), max(all_dates)

    if facts.opening_balance is not None:
        opening = facts.opening_balance
    elif records.closing_balance is not None:
        # Anchor to today's real bank balance. Transfers and owner draws are out of profit,
        # but they did move cash, so work back from what the bank actually holds now.
        opening = records.closing_balance - sum(t.amount for t in txs)
    else:
        opening = records.opening_balance
    if opening is None:
        opening = 0.0
        warnings.append("Starting cash balance unknown, so it's set to $0. Cash figures will be off "
                        "until you enter it or upload a bank export with a balance column.")
    if facts.labor_rate == 0 and any(j.labor_hours for j in jobs.values()):
        warnings.append("Jobs have labor hours but no labor rate was given, so labor costs are $0.")

    files = {
        "transactions.csv": _csv([{
            "date": t.date.isoformat(), "description": t.description[:200],
            "vendor": (t.vendor or t.description)[:80], "category": t.category,
            "amount": _money(t.amount), "job_id": ""} for t in sorted(txs, key=lambda t: t.date)],
            COLUMNS["transactions.csv"]),
        "jobs.csv": _csv([{
            "job_id": j.job_id, "customer": j.customer, "job_type": j.job_type,
            "start_date": j.start_date.isoformat(),
            "end_date": j.end_date.isoformat() if j.end_date else "",
            "quoted_price": _money(j.quoted_price), "labor_hours": f"{j.labor_hours:g}",
            "status": j.status} for j in jobs.values()], COLUMNS["jobs.csv"]),
        "invoices.csv": _csv([{
            "invoice_id": inv.invoice_id, "job_id": inv.job_ref, "customer": inv.customer,
            "issued": inv.issued.isoformat(), "due": max(inv.due, inv.issued).isoformat(),
            "amount": _money(inv.amount), "paid_amount": _money(min(inv.paid_amount, inv.amount)),
            "paid_date": inv.paid_date.isoformat() if inv.paid_amount > 0 and inv.paid_date else ""}
            for inv in invoices], COLUMNS["invoices.csv"]),
        "business.json": json.dumps({
            "name": facts.name, "currency": "USD", "accounting_basis": "cash",
            "opening_balance": round(opening, 2), "opening_balance_date": opening_date.isoformat(),
            "as_of_date": as_of.isoformat(), "labor_rate": facts.labor_rate,
            "tax_reserve_rate": facts.tax_reserve_rate}),
    }
    books = load_books_from_uploads(files)
    by_category: dict[str, float] = {}
    for t in txs:
        by_category[t.category] = round(by_category.get(t.category, 0.0) + t.amount, 2)
    summary = {"transactions": len(txs), "invoices": len(invoices), "jobs": len(jobs), "estimated_jobs": estimated,
               "excluded_transactions": len(excluded), "payment_dates_matched": matched,
               "date_range": [opening_date.isoformat(), as_of.isoformat()],
               "opening_balance": round(opening, 2),
               "bank_balance_now": records.closing_balance, "totals_by_category": by_category}
    return books, warnings, summary
