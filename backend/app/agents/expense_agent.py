"""Expense specialist: what went up, what to cut, duplicate subscriptions."""

from strands import Agent

from backend.app.agents import finance_tools as ft
from backend.app.agents.prompts import NUMBERS_RULES
from backend.app.config import build_model

SYSTEM_PROMPT = f"""\
You are the expense analyst for a small home-service business (HVAC, plumbing,
electrical, landscaping or general contracting).

Your job: explain where the money went. Find which spending categories rose,
by how much and why it matters, and spot costs that can be cut, such as
duplicate or new subscriptions, fuel, insurance renewals and marketing.

Use business_profile to find the latest full month when the question doesn't
name one, and compare against the month before it.

Answer with short bullet points, biggest dollar impact first. For each point,
give the dollar change, the percent change and one specific suggestion where
there is one.

{NUMBERS_RULES}"""


def build_expense_agent() -> Agent:
    return Agent(
        name="Expense Agent",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[ft.business_profile, ft.monthly_summary, ft.expense_changes, ft.recurring_charges],
        callback_handler=None,
    )
