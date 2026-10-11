"""The trade analyst: a specialist for the company's trades (HVAC, plumbing, electrical)."""

from strands import Agent

from backend.app.agents import finance_tools as ft
from backend.app.agents.prompts import BRIEF_RULES, ESTIMATED_JOBS, NUMBERS_RULES
from backend.app.config import build_model


def system_prompt(chosen) -> str:
    from backend.app.trades import names

    chosen = chosen if isinstance(chosen, (list, tuple)) else [chosen]
    advice = "\n\n".join(t.ADVICE for t in chosen)
    sections = "\n".join(f"- {build.__name__}: {build.__doc__}" for t in chosen for build in t.SECTIONS)
    return f"""\
You are the {names(chosen)} analyst for a small contracting business.

{advice}

Your tool trade_section returns these sections, each with headline numbers, a
table, a takeaway and notes:
{sections}

Answer with short bullet points, most important first, using the section numbers.
If a section says it needs more data, say what's missing.

{NUMBERS_RULES}

{BRIEF_RULES}

{ESTIMATED_JOBS}"""


def build_trade_agent(chosen) -> Agent:
    from backend.app.trades import names

    chosen = chosen if isinstance(chosen, (list, tuple)) else [chosen]
    return Agent(
        name=f"{names(chosen)} Analyst",
        model=build_model(),
        system_prompt=system_prompt(chosen),
        tools=[ft.business_profile, ft.trade_section],
        callback_handler=None,
    )
