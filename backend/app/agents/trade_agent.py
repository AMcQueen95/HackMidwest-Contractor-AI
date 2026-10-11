"""The trade analyst: a specialist that knows one trade's sections (HVAC first)."""

from strands import Agent

from backend.app.agents import finance_tools as ft
from backend.app.agents.prompts import NUMBERS_RULES
from backend.app.config import build_model


def system_prompt(trade) -> str:
    sections = "\n".join(f"- {build.__name__}: {build.__doc__}" for build in trade.SECTIONS)
    return f"""\
You are the {trade.NAME} analyst for a small {trade.NAME} business.

{trade.ADVICE}

Your tool trade_section returns these sections, each with headline numbers, a
table, a takeaway and notes:
{sections}

Answer with short bullet points, most important first, using the section numbers.
If a section says it needs more data, say what's missing.

{NUMBERS_RULES}"""


def build_trade_agent(trade) -> Agent:
    return Agent(
        name=f"{trade.NAME} Analyst",
        model=build_model(),
        system_prompt=system_prompt(trade),
        tools=[ft.business_profile, ft.trade_section],
        callback_handler=None,
    )
