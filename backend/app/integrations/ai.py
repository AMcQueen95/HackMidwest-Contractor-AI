"""The two import agents: one identifies what a file is, one categorizes transactions.

Both only describe data. Code reads and converts every value, so the agents
never produce a number that ends up in the books.
"""

import asyncio
import json
import logging
from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent

from backend.app.config import build_model
from backend.app.integrations.records import ALL_CATEGORIES, Transaction

log = logging.getLogger(__name__)


async def structured(role: str, system: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Ask a fresh agent for output in `schema`. Falls back to plain JSON if the
    model ends its turn without using the structured-output tool."""
    agent = Agent(model=build_model(role), system_prompt=system, callback_handler=None)
    try:
        return (await agent.invoke_async(prompt, structured_output_model=schema)).structured_output
    except Exception as e:  # noqa: BLE001
        log.warning("Structured output failed (%s); retrying as plain JSON", e)
    writer = Agent(model=build_model(role), callback_handler=None,
                   system_prompt=system + "\n\nReply with only the JSON object, no code fences.")
    raw = str(await writer.invoke_async(
        f"{prompt}\n\nJSON schema:\n{json.dumps(schema.model_json_schema())}")).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return schema.model_validate_json(raw)


# --- What is this file? -----------------------------------------------------------

class Columns(BaseModel):
    """The file's own header names for each field. Leave a field null if the file doesn't have it."""

    date: str | None = Field(None, description="Transaction date (prefer posted date)")
    description: str | None = Field(None, description="Transaction description or memo")
    vendor: str | None = Field(None, description="Payee, merchant or vendor name, if separate")
    amount: str | None = Field(None, description="Single signed or unsigned amount column")
    debit: str | None = Field(None, description="Money-out column, when money in and out are separate")
    credit: str | None = Field(None, description="Money-in column, when money in and out are separate")
    direction: str | None = Field(None, description="Column saying debit/credit or similar")
    balance: str | None = Field(None, description="Running account balance")
    category: str | None = Field(None, description="The source's own category or account name")
    job_ref: str | None = Field(None, description="On invoices: job or work order number")
    invoice_id: str | None = Field(None, description="Invoice number")
    customer: str | None = Field(None, description="Customer or client name")
    issued: str | None = Field(None, description="Invoice date")
    due: str | None = Field(None, description="Invoice due date")
    invoice_total: str | None = Field(None, description="Invoice total")
    paid_amount: str | None = Field(None, description="Amount paid so far")
    open_balance: str | None = Field(None, description="Amount still unpaid")
    paid_date: str | None = Field(None, description="Date paid")
    job_id: str | None = Field(None, description="On jobs: job or work order number")
    job_type: str | None = Field(None, description="Kind of work, service or job title")
    start_date: str | None = Field(None, description="Job start or scheduled date")
    end_date: str | None = Field(None, description="Job completion date")
    quoted_price: str | None = Field(None, description="Job price, quote or total")
    labor_hours: str | None = Field(None, description="Hours worked")
    status: str | None = Field(None, description="Job or invoice status")


class FileInterpretation(BaseModel):
    kind: Literal["transactions", "invoices", "jobs", "unknown"] = Field(
        description="transactions: bank, card or accounting ledger lines. invoices: bills sent to "
                    "customers. jobs: work orders or projects. unknown: anything else.")
    source: str = Field(description="Best guess at where it came from, e.g. 'Chase business checking "
                                    "export', 'QuickBooks Invoice List', 'Jobber jobs export'")
    account: Literal["bank", "credit_card", "accounting", "other"] = Field(
        "other", description="For transactions: bank account, credit card, or accounting software ledger")
    header_row: int = Field(description="0-based index, in the sample lines, of the column header row")
    columns: Columns
    amount_sign: Literal["inflow_positive", "outflow_positive", "split_columns", "direction_column"] = Field(
        "inflow_positive",
        description="How money direction is shown. inflow_positive: deposits positive, spending negative. "
                    "outflow_positive: charges positive, payments/refunds negative (typical for credit "
                    "cards). split_columns: separate debit and credit columns. direction_column: unsigned "
                    "amount plus a column saying debit/credit.")
    outflow_values: list[str] = Field(default_factory=list,
                                      description="For direction_column: values meaning money out, e.g. ['DEBIT']")
    day_first: bool = Field(False, description="True if dates are day/month/year")
    notes: str = Field("", description="Anything the owner should know about this file")


IDENTIFY_SYSTEM = """\
You identify financial exports for a small home-service business (HVAC, plumbing,
electrical, landscaping, roofing, remodeling). You get a file name and its first
lines. Work out what kind of file it is, which line is the header, which header
names hold which fields, and how money direction is shown. Use exact header
names from the file. Never invent a column. Bank exports sometimes have title or
account-summary lines above the header; QuickBooks reports often do too."""


async def identify(filename: str, sample_lines: list[str]) -> FileInterpretation:
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(sample_lines))
    return await structured("specialist", IDENTIFY_SYSTEM, f"File name: {filename}\n\nFirst lines:\n{numbered}",
                            FileInterpretation)


# --- Categorize transactions ---------------------------------------------------------

class Categorized(BaseModel):
    id: int
    vendor: str = Field(description="Clean, human vendor name, e.g. 'SQ *HVAC SUPPLY #12' -> 'HVAC Supply'")
    category: str


class CategorizedBatch(BaseModel):
    items: list[Categorized]


CATEGORIZE_SYSTEM = f"""\
You categorize bank and card transactions for a small home-service business.
For each one, give a clean vendor name and exactly one category key:

{chr(10).join(f"- {k}: {v}" for k, v in ALL_CATEGORIES.items())}

Money in (positive amounts) is usually income from customers, unless it is a
transfer between the business's own accounts, an owner contribution, a loan or
a refund. A refund from a supplier keeps that supplier's category. Payments to
a credit card company from a bank account are transfers. When a source category
is given, use it as a strong hint. When unsure between business categories,
choose overhead."""


async def categorize(transactions: list[Transaction], batch_size: int = 80, trade_hint: str = "") -> None:
    """Set vendor and category on each transaction, asking once per distinct description.
    trade_hint adds the owner's trade vocabulary (e.g. what HVAC purchases look like)."""
    keys, groups = [], {}
    for t in transactions:
        key = (t.description.strip().lower(), t.vendor.strip().lower(), t.hint.strip().lower(), t.amount > 0)
        if key not in groups:
            groups[key] = []
            keys.append(key)
        groups[key].append(t)

    async def run(batch: list[tuple]) -> dict[int, Categorized]:
        lines = []
        for i, key in batch:
            t = groups[key][0]
            lines.append(json.dumps({"id": i, "description": t.description, "vendor": t.vendor or None,
                                     "source_category": t.hint or None,
                                     "direction": "in" if t.amount > 0 else "out",
                                     "account": t.account}))
        result = await structured("specialist", CATEGORIZE_SYSTEM + (f"\n\n{trade_hint}" if trade_hint else ""),
                                  "Categorize these transactions:\n" + "\n".join(lines), CategorizedBatch)
        return {item.id: item for item in result.items}

    indexed = list(enumerate(keys))
    batches = [indexed[i:i + batch_size] for i in range(0, len(indexed), batch_size)]
    answers: dict[int, Categorized] = {}
    for result in await asyncio.gather(*(run(b) for b in batches)):
        answers.update(result)

    for i, key in indexed:
        answer = answers.get(i)
        for t in groups[key]:
            category = answer.category.strip().lower() if answer else ""
            t.category = category if category in ALL_CATEGORIES else ("income" if t.amount > 0 else "overhead")
            t.vendor = (answer.vendor.strip() if answer and answer.vendor.strip() else t.vendor or t.description)
