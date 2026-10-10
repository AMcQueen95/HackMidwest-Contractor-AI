"""Offline agent checks: no model calls, no API key needed."""

from backend.app.agents import finance_tools as ft
from backend.app.agents.cash_flow_agent import build_cash_flow_agent
from backend.app.agents.cfo_agent import build_cfo_agent
from backend.app.agents.expense_agent import build_expense_agent
from backend.app.agents.job_profitability_agent import build_job_profitability_agent


def test_profile_finds_latest_full_month():
    profile = ft.business_profile()
    assert profile["name"] == "Ridgeline Heating & Air"
    assert profile["latest_full_month"] == "2026-09"


def test_tools_return_the_demo_story():
    """The answers the pitch depends on, read through the agent tools."""
    assert ft.monthly_summary("2026-09")["profit"] == -7830
    assert {j["customer"] for j in ft.losing_jobs()["jobs"]} >= {"Westport Dental"}
    assert ft.receivables()["total_outstanding"] == 21000
    assert ft.affordability(15000)["can_afford_now"] is False


def test_agents_have_the_right_tools():
    assert set(build_expense_agent().tool_names) >= {"expense_changes", "recurring_charges"}
    assert set(build_job_profitability_agent().tool_names) >= {"losing_jobs", "margin_by_job_type"}
    assert set(build_cash_flow_agent().tool_names) >= {"receivables", "affordability"}
    assert set(build_cfo_agent().tool_names) >= {
        "expense_agent", "job_profitability_agent", "cash_flow_agent", "business_profile"}


# --- Report, fallback and sessions (fake agents, no model calls) ----------------

import pytest

from backend.app import finance
from backend.app.agents import cfo_agent
from backend.app.agents.schemas import Issue, Recommendation, ReportNarrative

NARRATIVE = ReportNarrative(
    summary="Revenue was $999,999 and profit was $1.",  # wrong on purpose
    issues=[Issue(title="Materials up", detail="Up $4,000.", agent="expense")],
    recommendations=[Recommendation(action="Call Westport.", impact="$12,000 owed.")],
)


class FakeAgent:
    """Stands in for a Strands Agent: records prompts and returns a canned reply."""

    def __init__(self, reply="ok", messages=None, error=None):
        self.prompts, self.reply, self.messages, self.error = [], reply, messages or [], error

    def __call__(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture(autouse=True)
def fresh_sessions():
    cfo_agent._sessions.clear()
    yield
    cfo_agent._sessions.clear()


def test_report_figures_come_from_code_not_the_model(monkeypatch):
    monkeypatch.setattr(cfo_agent, "_write_narrative", lambda month: NARRATIVE)
    report = cfo_agent.financial_health_report()
    summary = finance.monthly_summary(ft.get_books(), "2026-09")

    assert report.month == "2026-09"
    assert (report.revenue, report.expenses, report.profit) == (
        summary["revenue"], summary["expenses"], summary["profit"])
    assert report.margin_pct == round(summary["profit"] / summary["revenue"] * 100, 1)
    assert report.issues == NARRATIVE.issues


def test_report_falls_back_to_plain_json_when_structured_output_fails(monkeypatch):
    cfo = FakeAgent(
        error=RuntimeError("forced tool call rejected"),
        messages=[{"role": "user", "content": [{"text": "Write the report"}]},
                  {"role": "assistant", "content": [{"text": "Materials rose $4,000."}]}],
    )
    writer = FakeAgent(reply=f"```json\n{NARRATIVE.model_dump_json()}\n```")
    monkeypatch.setattr(cfo_agent, "build_cfo_agent", lambda stream=False: cfo)
    monkeypatch.setattr(cfo_agent, "build_model", lambda role="specialist": None)
    monkeypatch.setattr(cfo_agent, "Agent", lambda **kwargs: writer)

    assert cfo_agent._write_narrative("2026-09") == NARRATIVE
    assert "Materials rose $4,000." in writer.prompts[0]  # the writer only sees the CFO's findings


def test_report_fallback_refuses_to_invent_findings(monkeypatch):
    cfo = FakeAgent(error=RuntimeError("failed before any findings"))
    monkeypatch.setattr(cfo_agent, "build_cfo_agent", lambda stream=False: cfo)

    with pytest.raises(RuntimeError, match="no findings"):
        cfo_agent._write_narrative("2026-09")


def test_follow_up_questions_reuse_the_session(monkeypatch):
    built = []
    monkeypatch.setattr(cfo_agent, "build_cfo_agent",
                        lambda stream=False: built.append(FakeAgent(reply="answer")) or built[-1])

    first = cfo_agent.ask("Why did profit drop?")
    follow_up = cfo_agent.ask("What about fuel?", session_id=first.session_id)
    other = cfo_agent.ask("Who owes me money?")

    assert follow_up.session_id == first.session_id
    assert other.session_id != first.session_id
    assert len(built) == 2
    assert built[0].prompts == ["Why did profit drop?", "What about fuel?"]
    assert built[1].prompts == ["Who owes me money?"]
