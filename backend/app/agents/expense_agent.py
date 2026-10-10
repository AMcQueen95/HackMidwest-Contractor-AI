import json

from strands import Agent, tool

from app.agents import finance_api
from app.agents.model import build_model

SYSTEM_PROMPT = """You are the expense analyst for a small home-service business.
You answer questions about spending: what went up, what can be cut, and
which subscriptions overlap. Get every number from your tools and never
estimate one. Months are written YYYY-MM. Reply with the figures you found
and a one-line explanation of each, in plain language an owner can act on."""


@tool
def monthly_summary(month: str) -> str:
    """Revenue, expenses and profit for one month.

    Args:
        month: Month as YYYY-MM, e.g. 2026-09.
    """
    return json.dumps(finance_api.monthly_summary(month))


@tool
def expense_changes(month: str) -> str:
    """Expense categories that changed most versus the previous month.

    Args:
        month: Month as YYYY-MM, e.g. 2026-09.
    """
    return json.dumps(finance_api.expense_changes(month))


@tool
def recurring_charges() -> str:
    """Recurring charges such as subscriptions, with likely duplicates flagged."""
    return json.dumps(finance_api.recurring_charges())


TOOLS = [monthly_summary, expense_changes, recurring_charges]


def build_agent() -> Agent:
    return Agent(
        name="expense_analyst",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        callback_handler=None,
    )
