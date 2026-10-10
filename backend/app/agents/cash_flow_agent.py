"""Cash flow specialist: cash on hand, who owes money, can we afford X."""

from strands import Agent

from backend.app.agents import finance_tools as ft
from backend.app.agents.prompts import NUMBERS_RULES
from backend.app.config import build_model

SYSTEM_PROMPT = f"""\
You are the cash flow analyst for a small home-service business.

Your job: say how much cash the business has, who owes it money and for how
long, and whether it can afford a purchase or a new hire without running short.

For any "can I afford X" question, call affordability with the dollar amount.
Give a clear yes, no, or "yes, once these invoices are collected", followed
by the numbers behind it. For a hire, ask the affordability tool about a
realistic three-month cost if the question gives one; otherwise say what
salary figure you'd need.

For receivables, list who owes what, oldest overdue first, and suggest which
to chase this week.

{NUMBERS_RULES}"""


def build_cash_flow_agent() -> Agent:
    return Agent(
        name="Cash Flow Agent",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[ft.business_profile, ft.monthly_summary, ft.cash_balance, ft.receivables, ft.affordability],
        callback_handler=None,
    )
