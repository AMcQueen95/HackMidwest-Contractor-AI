import json

from strands import Agent, tool

from app.agents import finance_api
from app.agents.model import build_model

SYSTEM_PROMPT = """You are the job costing analyst for a small home-service business.
You answer which jobs and job types make or lose money, and why. Get every
number from your tools and never estimate one. When a job lost money, say
what drove the loss (materials, labor, or pricing) and how to bid it
differently next time."""


@tool
def job_profitability(job_id: str) -> str:
    """Revenue, material and labor cost, profit and margin for one job.

    Args:
        job_id: Job ID such as J-1042.
    """
    return json.dumps(finance_api.job_profitability(job_id))


@tool
def losing_jobs() -> str:
    """All jobs with negative profit."""
    return json.dumps(finance_api.losing_jobs())


@tool
def margin_by_job_type() -> str:
    """Revenue, profit and margin grouped by job type."""
    return json.dumps(finance_api.margin_by_job_type())


TOOLS = [job_profitability, losing_jobs, margin_by_job_type]


def build_agent() -> Agent:
    return Agent(
        name="job_profitability_analyst",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        callback_handler=None,
    )
