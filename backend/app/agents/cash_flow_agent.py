import json

from strands import Agent, tool

from app.agents import finance_api
from app.agents.model import build_model

SYSTEM_PROMPT = """You are the cash flow analyst for a small home-service business.
You answer how much cash is on hand, who owes money, and whether a purchase
is affordable. Get every number from your tools and never estimate one.
For a purchase, say whether to pay cash, wait for receivables, or finance it,
and why."""


@tool
def cash_balance() -> str:
    """Cash on hand and average monthly expenses as of the books date."""
    return json.dumps(finance_api.cash_balance())


@tool
def receivables() -> str:
    """Unpaid invoices with customer, amount and days overdue."""
    return json.dumps(finance_api.receivables())


@tool
def affordability(amount: float) -> str:
    """Whether the business can spend this amount now without dropping below its cash reserve.

    Args:
        amount: Purchase amount in dollars.
    """
    return json.dumps(finance_api.affordability(amount))


TOOLS = [cash_balance, receivables, affordability]


def build_agent() -> Agent:
    return Agent(
        name="cash_flow_analyst",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        callback_handler=None,
    )
