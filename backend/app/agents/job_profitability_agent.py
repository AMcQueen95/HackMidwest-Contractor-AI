"""Job profitability specialist: which jobs and job types make or lose money."""

from strands import Agent

from backend.app.agents import finance_tools as ft
from backend.app.agents.prompts import BRIEF_RULES, ESTIMATED_JOBS, NUMBERS_RULES
from backend.app.config import build_model

SYSTEM_PROMPT = f"""\
You are the job costing analyst for a small home-service business.

Your job: say which jobs and job types make money and which lose it, after
materials, permits, equipment rentals and labor. When a job lost money, point
to the cause the numbers show, such as direct costs over the quote or labor
hours far above normal for that job type, and suggest how to quote or run that
kind of job differently next time (escalation clauses on fixed bids, callback
policies, pricing floors).

Answer with short bullet points, worst first, naming the job ID and customer.

{NUMBERS_RULES}

{BRIEF_RULES}

{ESTIMATED_JOBS}"""


def build_job_profitability_agent() -> Agent:
    return Agent(
        name="Job Profitability Agent",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[ft.business_profile, ft.job_profitability, ft.losing_jobs, ft.margin_by_job_type],
        callback_handler=None,
    )
