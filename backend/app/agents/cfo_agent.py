"""CFO Advisor: the orchestrator. Each specialist agent is one of its tools."""

import json
import logging
import uuid

from strands import Agent, tool

from backend.app.agents import finance_tools as ft
from backend.app.agents.cash_flow_agent import build_cash_flow_agent
from backend.app.agents.events import emit
from backend.app.agents.expense_agent import build_expense_agent
from backend.app.agents.job_profitability_agent import build_job_profitability_agent
from backend.app.agents.trade_agent import build_trade_agent
from backend.app.agents.prompts import NUMBERS_RULES
from backend.app.agents.schemas import AskResponse, FinancialHealthReport, ReportNarrative
from backend.app.config import build_model

log = logging.getLogger(__name__)


# --- Specialists as tools --------------------------------------------------------

async def _consult(name: str, build, question: str) -> str:
    log.info("CFO -> %s: %s", name, question)
    answer = str(await build().invoke_async(question))
    emit({"type": "status", "text": f"Consulted the {_ANALYSTS[name]}"})
    return answer


_ANALYSTS = {"Expense Agent": "expense analyst", "Job Profitability Agent": "job costing analyst",
             "Cash Flow Agent": "cash flow analyst", "Trade Agent": "trade analyst"}


@tool
async def expense_agent(question: str) -> str:
    """Ask the expense analyst about spending: which categories rose and why,
    what to cut, and duplicate or new subscriptions.

    Args:
        question: A specific question, including the month if known.
    """
    return await _consult("Expense Agent", build_expense_agent, question)


@tool
async def job_profitability_agent(question: str) -> str:
    """Ask the job costing analyst which jobs or job types made or lost money and why.

    Args:
        question: A specific question, including the month if known.
    """
    return await _consult("Job Profitability Agent", build_job_profitability_agent, question)


@tool
async def cash_flow_agent(question: str) -> str:
    """Ask the cash flow analyst about cash on hand, unpaid invoices, and whether
    a purchase or hire is affordable.

    Args:
        question: A specific question. Include dollar amounts for purchases.
    """
    return await _consult("Cash Flow Agent", build_cash_flow_agent, question)


@tool
async def trade_agent(question: str) -> str:
    """Ask the trade analyst (the HVAC, plumbing or electrical analyst) about this
    trade's own measures. What it covers is listed in your instructions.

    Args:
        question: A specific question, including the month if known.
    """
    from backend.app import trades

    trade = trades.current()
    if trade is None:
        return "No trade is set for this business."
    log.info("CFO -> %s Analyst: %s", trade.NAME, question)
    answer = str(await build_trade_agent(trade).invoke_async(question))
    emit({"type": "status", "text": f"Consulted the {trade.NAME} analyst"})
    return answer


# --- The CFO ---------------------------------------------------------------------

SYSTEM_PROMPT = f"""\
You are the CFO for a small home-service business. The owner runs jobs all day
and isn't a finance person. Talk to them like a trusted advisor: plain words,
no jargon, straight answers.

You have three specialist analysts, available as tools:
- expense_agent: spending changes, cuts, subscriptions
- job_profitability_agent: which jobs and job types make or lose money
- cash_flow_agent: cash, unpaid invoices, whether a purchase or hire is affordable

How to work:
1. Call business_profile if you need to know which month is "this month".
2. Send each relevant specialist a specific question. Broad questions like "why
   did profit drop?" usually need all three; a narrow one may need just one.
3. Combine their findings into one answer. Lead with the direct answer in one or
   two sentences, then the main reasons, biggest dollar impact first, then two
   to four concrete next steps.

Keep it short enough to read on a phone between jobs. It shows in a chat window,
so write plain text: short paragraphs separated by blank lines, and lists as
lines starting with "- ". No bold, headings, tables or other markdown. Don't
announce what you're about to look up; call the tools, then answer.

{NUMBERS_RULES}"""


def build_cfo_agent(stream: bool = False, messages: list | None = None) -> Agent:
    """stream=True prints the answer to stdout as it's generated (for the CLI).
    messages seeds the conversation history, e.g. with the month's report.
    When the owner picked a trade, the CFO gets that trade's advice and analyst."""
    from backend.app import trades

    kwargs = {} if stream else {"callback_handler": None}
    trade = trades.current()
    tools = [ft.business_profile, ft.monthly_summary, expense_agent, job_profitability_agent, cash_flow_agent]
    prompt = SYSTEM_PROMPT
    if trade is not None:
        tools.append(trade_agent)
        covers = "\n".join(f"- {build.__doc__}" for build in trade.SECTIONS)
        prompt += (f"\n\n{trade.ADVICE}\n\nYou also have a {trade.NAME} analyst (trade_agent). It has numbers "
                   f"the other analysts don't:\n{covers}\nAsk it whenever a question touches any of these, "
                   f"alongside the other analysts as needed.")
    return Agent(
        name="CFO Advisor",
        model=build_model("cfo"),
        messages=messages,
        system_prompt=prompt,
        tools=tools,
        **kwargs,
    )


# --- Entry points for the API ------------------------------------------------------

_sessions: dict[str, Agent] = {}


def ask(question: str, session_id: str | None = None) -> AskResponse:
    """Answer an owner's question. Reuse session_id to keep follow-up context."""
    session_id = session_id or uuid.uuid4().hex
    if session_id not in _sessions:
        _sessions[session_id] = build_cfo_agent()
    agent = _sessions[session_id]
    return AskResponse(answer=str(agent(question)).strip(), session_id=session_id)


def financial_health_report(month: str | None = None) -> FinancialHealthReport:
    """The monthly report card. Figures come from code; the agents write the rest."""
    books = ft.get_books()
    month = month or ft.latest_full_month(books)
    summary = ft.finance.monthly_summary(books, month)
    revenue, profit = summary["revenue"], summary["profit"]

    narrative = _write_narrative(month)
    return FinancialHealthReport(
        business=books.business["name"],
        month=month,
        revenue=revenue,
        expenses=summary["expenses"],
        profit=profit,
        margin_pct=round(profit / revenue * 100, 1) if revenue else None,
        **narrative.model_dump(),
    )


def _write_narrative(month: str) -> ReportNarrative:
    agent = build_cfo_agent()
    prompt = (f"Write the Financial Health report for {month}. Consult all three specialists so "
              f"the issues cover spending, job profitability and cash. When you have their "
              f"findings, finish by calling the ReportNarrative tool. Don't write the report as text.")
    try:
        return agent(prompt, structured_output_model=ReportNarrative).structured_output
    except Exception as e:  # noqa: BLE001
        # If the model ends its turn without calling the output tool, Strands retries with a
        # forced tool call, which Claude Opus 5.5 rejects. Fall back to asking for plain JSON.
        log.warning("Structured output failed (%s); retrying as plain JSON", e)

    findings = "\n\n".join(
        block["text"] for msg in agent.messages if msg["role"] == "assistant"
        for block in msg["content"] if "text" in block
    ).strip()
    if not findings:
        raise RuntimeError(f"The CFO agent produced no findings for {month}")
    writer = Agent(model=build_model("cfo"), callback_handler=None,
                   system_prompt="You turn a CFO's findings into JSON. Output only the JSON object, "
                                 "no code fences. Use only facts and figures from the findings.")
    raw = str(writer(f"JSON schema:\n{json.dumps(ReportNarrative.model_json_schema())}\n\n"
                     f"Findings:\n{findings}")).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return ReportNarrative.model_validate_json(raw)
