"""CFO Advisor: the orchestrator. Each specialist agent is one of its tools."""

from strands import Agent, tool

from app.agents import cash_flow_agent, expense_agent, job_profitability_agent
from app.agents.model import build_model

SYSTEM_PROMPT = """You are the CFO for a small home-service business (HVAC, plumbing,
electrical, landscaping). The owner is busy and not an accountant.

You have three specialist analysts as tools. Ask each one only what it
covers, and call several when a question spans their areas. For "why did
profit drop" or a health check, consult all three. Use only figures the
analysts return; never invent or estimate a number.

Answer in this shape:
- One or two sentences answering the question directly, with the key numbers.
- "Issues": the problems behind it, biggest dollar impact first.
- "Recommendations": specific actions for this week, each with its dollar effect where known.
Keep it short. Use dollars rounded to the nearest dollar."""


def _ask(build_agent, question: str) -> str:
    # A fresh specialist per call keeps each consultation independent.
    return str(build_agent()(question))


@tool
def expense_analyst(question: str) -> str:
    """Ask the expense analyst about monthly revenue, expenses and profit,
    which expense categories rose, and recurring or duplicate subscriptions.

    Args:
        question: A specific question, including the month (YYYY-MM) if relevant.
    """
    return _ask(expense_agent.build_agent, question)


@tool
def job_profitability_analyst(question: str) -> str:
    """Ask the job costing analyst which jobs or job types make or lose money and why.

    Args:
        question: A specific question, naming a job ID if relevant.
    """
    return _ask(job_profitability_agent.build_agent, question)


@tool
def cash_flow_analyst(question: str) -> str:
    """Ask the cash flow analyst about cash on hand, unpaid invoices and who owes
    money, and whether a purchase is affordable.

    Args:
        question: A specific question, including any purchase amount.
    """
    return _ask(cash_flow_agent.build_agent, question)


TOOLS = [expense_analyst, job_profitability_analyst, cash_flow_analyst]


def build_agent(callback_handler=None) -> Agent:
    return Agent(
        name="cfo_advisor",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        callback_handler=callback_handler,
    )


def ask(question: str) -> str:
    """Answer one owner question. This is what the API calls."""
    return str(build_agent()(question))
