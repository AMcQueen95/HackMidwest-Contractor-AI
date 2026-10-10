"""Live smoke test: real model calls through the Anthropic API.

Skipped by default. Costs a few cents per run. Run before the demo with:

    RUN_LIVE_TESTS=1 python -m pytest backend/tests/test_agents_live.py -v
"""

import asyncio
import itertools
import os
import re
from functools import cache
from pathlib import Path

import pytest
from dotenv import dotenv_values

from backend.app import finance
from backend.app.agents import ask, financial_health_report, stream_narrative
from backend.app.agents import finance_tools as ft

pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1",
                                reason="set RUN_LIVE_TESTS=1 to call the real model")


@pytest.fixture(autouse=True)
def real_api_key(monkeypatch):
    """conftest sets a placeholder key; swap in the one from backend/.env."""
    key = os.getenv("LIVE_ANTHROPIC_API_KEY") or dotenv_values(
        Path(__file__).resolve().parents[1] / ".env").get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("no ANTHROPIC_API_KEY in backend/.env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)


def _plain(text: str) -> str:
    return text.replace(",", "").lower()


def _numbers(value) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [abs(float(value))]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in _numbers(v)]
    return []


@cache
def _traceable() -> frozenset[float]:
    """Every figure the tools can return for the sample books, plus any single
    sum or difference of two of them (the comparisons agents may state)."""
    books = ft.get_books()
    results = [books.business, finance.cash_balance(books), finance.receivables(books),
               finance.affordability(books, 15000), ft.recurring_charges("2026-09")]
    for month in ("2026-08", "2026-09"):
        results += [getattr(finance, name)(books, month) for name in (
            "monthly_summary", "expense_changes", "recurring_charges",
            "job_profitability", "losing_jobs", "margin_by_job_type")]
    base = {round(n, 2) for n in _numbers(results)} | {15000.0}
    pairs = {round(a + b, 2) for a, b in itertools.combinations(base, 2)}
    pairs |= {round(abs(a - b), 2) for a, b in itertools.combinations(base, 2)}
    return frozenset(base | pairs)


def assert_figures_traceable(text: str):
    """Fail if the text states a dollar figure the books can't account for."""
    known = _traceable()
    stated = [float(m.replace(",", "")) for m in re.findall(r"\$\s?(\d[\d,]*(?:\.\d+)?)(?!\s?[kKmM%])", text)]
    unknown = [n for n in stated if not any(abs(n - k) < 1 for k in known)]
    assert not unknown, f"untraceable dollar figures {unknown} in:\n{text}"


# Facts each answer must contain, from the verified sample books.
DEMO = [
    ("Why did profit drop this month?", ["7830"]),
    ("Which jobs are losing money?", ["westport", "1232"]),
    ("Which customers still owe me money?", ["westport", "brookside", "21000"]),
    ("What expenses increased the most?", ["materials", "4000"]),
]


@pytest.mark.parametrize("question,facts", DEMO, ids=[q for q, _ in DEMO])
def test_demo_answer_has_the_key_facts(question, facts):
    raw = ask(question).answer
    answer = _plain(raw)
    missing = [f for f in facts if f not in answer]
    assert not missing, f"missing {missing} in answer:\n{answer}"
    assert_figures_traceable(raw)


def test_equipment_purchase_is_not_affordable_today():
    raw = ask("Can I afford a $15,000 equipment purchase?").answer
    assert_figures_traceable(raw)
    answer = _plain(raw)
    assert re.search(r"\b(no|not|wait|hold off|don't)\b", answer), answer
    assert "westport" in answer or "21000" in answer, "should say collecting invoices changes the answer"


def test_monthly_report():
    report = financial_health_report("2026-09")
    assert report.profit == -7830
    assert len(report.issues) >= 3 and len(report.recommendations) >= 3
    assert any("westport" in _plain(i.detail + i.title) for i in report.issues)
    assert_figures_traceable(report.model_dump_json())


def test_subscription_savings_use_each_apps_own_cost():
    raw = ask("Which software subscriptions should I cancel, and how much would that save each month?").answer
    answer = _plain(raw)
    assert "398" in answer or "169" in answer, answer
    # $567 is both apps together. It may be mentioned only as that combined total.
    for sentence in re.split(r"(?<=[.!?])\s+|\n", answer):
        if "567" in sentence:
            assert re.search(r"together|total|combined|both", sentence), f"$567 used as a saving:\n{raw}"
    assert_figures_traceable(raw)


def test_written_report_streams_in_the_ui_format_with_traceable_figures():
    async def collect():
        parts = []
        async for chunk in stream_narrative("2026-09"):
            parts.clear() if chunk is None else parts.append(chunk)
        return "".join(parts)

    text = asyncio.run(collect())
    assert re.search(r"^Issues\s*$", text, re.M) and re.search(r"^Recommendations\s*$", text, re.M), text
    assert "**" not in text
    assert_figures_traceable(text)
