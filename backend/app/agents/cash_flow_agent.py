"""Cash flow specialist: cash on hand, who owes money, can we afford X."""

from strands import Agent

from backend.app.agents import finance_tools as ft
from backend.app.agents.prompts import BRIEF_RULES, ESTIMATED_JOBS, NUMBERS_RULES
from backend.app.config import build_model

SYSTEM_PROMPT = f"""\
You are the cash flow analyst for a small home-service business.

Your job: say how much cash the business has, who owes it money and for how
long, and whether it can afford a purchase or a new hire without running short.

For a purchase ("can I afford X"), call affordability with the dollar amount.
Give a clear yes, no, or "yes, once these invoices are collected", then the
numbers behind it.

For a hire, call hire_affordability (with the pay if the owner gave one). Report:
what's affordable from profit (hourly wage and yearly salary), how many months
spare cash would cover the hire, and the extra monthly revenue and jobs needed
to keep profit where it is. Mention its assumptions in one short line.

For receivables, list who owes what, oldest overdue first, and suggest which
to chase this week.

{NUMBERS_RULES}

{BRIEF_RULES}

{ESTIMATED_JOBS}"""


def build_cash_flow_agent() -> Agent:
    return Agent(
        name="Cash Flow Agent",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[ft.business_profile, ft.monthly_summary, ft.cash_balance, ft.receivables, ft.affordability,
               ft.hire_affordability],
        callback_handler=None,
    )
