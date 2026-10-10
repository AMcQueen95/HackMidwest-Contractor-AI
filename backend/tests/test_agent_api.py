"""API and streaming checks with fake agents: no model calls."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.agents import streaming
from backend.app.agents.events import emit
from backend.app.main import COOKIE_NAME, create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


MOCK = json.loads(
    (
        Path(__file__).resolve().parents[2] / "frontend/src/api/mock/books.json"
    ).read_text()
)


def sse(response) -> list[dict]:
    return [
        json.loads(line[6:])
        for line in response.iter_lines()
        if line.startswith("data: ")
    ]


@pytest.fixture(autouse=True)
def clean_state():
    streaming.reset_caches()
    yield
    streaming.reset_caches()


@pytest.mark.parametrize("month", sorted(MOCK))
def test_report_matches_the_data_the_frontend_was_built_on(month, client):
    report = client.get(f"/api/report?month={month}").json()
    assert report["month"] == month and report["months"] == sorted(MOCK)
    assert all(report[key] == value for key, value in MOCK[month].items())


def test_report_defaults_to_latest_month_and_affordability_checks_amount(client):
    assert client.get("/api/report").json()["month"] == "2026-09"
    assert client.get("/api/affordability?amount=15000").json()["shortfall"] == 16447
    assert client.get("/api/affordability?amount=-1").status_code == 422


def test_bad_requests_are_rejected(client):
    assert client.post("/api/ask", json={"question": "  "}).status_code == 422
    response = client.post("/api/upload", files=[("files", ("jobs.csv", b"job_id\n"))])
    assert (
        response.status_code == 422 and "transactions.csv" in response.json()["detail"]
    )


class FakeStreamingAgent:
    """Streams like a Strands agent: text, a tool call that emits a status and two
    duplicate cards, then the real answer."""

    async def stream_async(self, prompt):
        yield {"data": "Let me check. "}
        yield {"current_tool_use": {"name": "cash_flow_agent"}}
        await asyncio.to_thread(
            emit, {"type": "card", "card": {"type": "receivables", "data": {"n": 1}}}
        )
        await asyncio.to_thread(
            emit, {"type": "card", "card": {"type": "receivables", "data": {"n": 2}}}
        )
        await asyncio.to_thread(
            emit, {"type": "status", "text": "Consulted the cash flow analyst"}
        )
        yield {"data": "Westport owes "}
        yield {"data": "$12,000."}


def test_ask_streams_events_in_the_frontend_shape(monkeypatch, client):
    monkeypatch.setattr(
        streaming, "build_cfo_agent", lambda **kwargs: FakeStreamingAgent()
    )
    events = sse(client.post("/api/ask", json={"question": "Who owes me money?"}))

    assert [e["type"] for e in events] == [
        "session",
        "text",
        "text_reset",
        "card",
        "status",
        "text",
        "text",
        "done",
    ]
    assert [e for e in events if e["type"] == "card"][0]["card"]["data"] == {
        "n": 1
    }  # duplicates dropped
    text = "".join(
        e["text"]
        for e in events[events.index({"type": "text_reset"}) :]
        if e["type"] == "text"
    )
    assert text == "Westport owes $12,000."


def test_new_chat_is_seeded_with_the_cached_report(monkeypatch, client):
    seen = {}

    def build(messages=None, **kwargs):
        seen["messages"] = messages
        return FakeStreamingAgent()

    monkeypatch.setattr(streaming, "build_cfo_agent", build)
    client.get("/api/report")
    dataset = client.app.state.datasets.get(client.cookies.get(COOKIE_NAME))
    dataset.agent_state.narratives["2026-09"] = (
        "September lost $7,830.\n\nIssues\n- Westport"
    )
    sse(
        client.post(
            "/api/ask", json={"question": "More on Westport?", "month": "2026-09"}
        )
    )
    assert seen["messages"][-1]["content"][0]["text"].startswith(
        "September lost $7,830."
    )


def test_narrative_streams_once_then_replays_from_cache(monkeypatch, client):
    calls = []

    def build(**kwargs):
        calls.append(1)
        return FakeStreamingAgent()

    monkeypatch.setattr(streaming, "build_cfo_agent", build)
    events = sse(client.get("/api/report/narrative?month=2026-09"))
    after_reset = events[events.index({"reset": True}) + 1 :]
    first = "".join(e.get("text", "") for e in after_reset)
    second = "".join(
        e.get("text", "")
        for e in sse(client.get("/api/report/narrative?month=2026-09"))
    )
    assert (
        first == second == "Westport owes $12,000."
    )  # preamble before the tool call dropped
    assert len(calls) == 1
