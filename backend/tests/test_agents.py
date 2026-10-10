"""Agent wiring tests. These never call Bedrock."""

import json

import pytest

from app.agents import cash_flow_agent, cfo_agent, expense_agent, finance_api, job_profitability_agent


@pytest.fixture(autouse=True)
def aws_region(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")


@pytest.mark.parametrize(
    "module, expected",
    [
        (expense_agent, {"monthly_summary", "expense_changes", "recurring_charges"}),
        (job_profitability_agent, {"job_profitability", "losing_jobs", "margin_by_job_type"}),
        (cash_flow_agent, {"cash_balance", "receivables", "affordability"}),
        (cfo_agent, {"expense_analyst", "job_profitability_analyst", "cash_flow_analyst"}),
    ],
)
def test_agents_have_their_tools(module, expected):
    assert set(module.build_agent().tool_names) == expected


def test_specialist_tools_return_json():
    summary = json.loads(expense_agent.monthly_summary("2026-09"))
    assert summary["profit"] == summary["revenue"] - summary["expenses"]

    losing = json.loads(job_profitability_agent.losing_jobs())
    assert all(job["profit"] < 0 for job in losing["jobs"])

    check = json.loads(cash_flow_agent.affordability(15_000))
    assert check["cash_after_purchase"] == check["cash"] - 15_000


def test_cfo_tools_delegate_to_specialists(monkeypatch):
    asked = {}

    def fake_builder(name):
        def build():
            def run(question):
                asked[name] = question
                return f"{name} answer"
            return run
        return build

    monkeypatch.setattr(expense_agent, "build_agent", fake_builder("expense"))
    monkeypatch.setattr(cash_flow_agent, "build_agent", fake_builder("cash"))

    assert cfo_agent.expense_analyst("What rose in 2026-09?") == "expense answer"
    assert cfo_agent.cash_flow_analyst("Can we afford $15,000?") == "cash answer"
    assert asked == {"expense": "What rose in 2026-09?", "cash": "Can we afford $15,000?"}


def test_stubs_are_reported_until_finance_lands():
    assert "monthly_summary" in finance_api.using_stubs()
