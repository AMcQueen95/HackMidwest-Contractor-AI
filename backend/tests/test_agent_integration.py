"""Combined uploads and streamed agents, without calling a model provider."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.agents import finance_tools as ft, streaming
from backend.app.main import COOKIE_NAME, create_app
from backend.tests.test_agent_api import sse
from backend.tests.test_api import multipart


class BooksAgent:
    def __init__(self, barrier=None):
        self.barrier = barrier
        self.questions = []

    async def stream_async(self, prompt):
        self.questions.append(prompt)
        if self.barrier:
            await asyncio.to_thread(self.barrier.wait, 5)
        # Strands tools execute in threads with the current context copied.
        expenses = await asyncio.to_thread(
            lambda: ft.monthly_summary("2026-09")["expenses"]
        )
        yield {"data": f"Expenses are ${expenses:,.0f}."}


def ask(client, session=None):
    response = client.post(
        "/api/ask",
        json={
            "question": "What are my expenses?",
            "month": "2026-09",
            "session_id": session,
        },
    )
    response.raise_for_status()
    events = sse(response)
    return events[0]["session_id"], "".join(e.get("text", "") for e in events)


@pytest.fixture
def changed(sample_files):
    return sample_files | {
        "transactions.csv": sample_files["transactions.csv"].replace(
            "insurance,-1260,", "insurance,-1500,"
        )
    }


def test_sample_browsers_have_separate_chat_history(monkeypatch):
    built = []
    monkeypatch.setattr(
        streaming,
        "build_cfo_agent",
        lambda **kw: built.append(BooksAgent()) or built[-1],
    )
    app = create_app()
    with TestClient(app) as first, TestClient(app) as second:
        session, _ = ask(first)
        reused, _ = ask(first, session)
        other, _ = ask(second, session)
        assert reused == session and other != session
        assert len(built) == 2
        assert len(built[0].questions) == 2 and len(built[1].questions) == 1
        assert first.cookies[COOKIE_NAME] != second.cookies[COOKIE_NAME]


def test_upload_and_reset_replace_ai_cache_and_chat(monkeypatch, changed):
    built = []
    monkeypatch.setattr(
        streaming,
        "build_cfo_agent",
        lambda **kw: built.append(BooksAgent()) or built[-1],
    )
    with TestClient(create_app()) as client:
        session, text = ask(client)
        assert "$52,900" in text
        first = sse(client.get("/api/report/narrative?month=2026-09"))
        again = sse(client.get("/api/report/narrative?month=2026-09"))
        assert first == again and len(built) == 2
        client.post("/api/upload", files=multipart(changed)).raise_for_status()
        new, text = ask(client, session)
        assert new != session and "$53,140" in text
        report = sse(client.get("/api/report/narrative?month=2026-09"))
        assert "$53,140" in "".join(e.get("text", "") for e in report)
        assert len(built) == 4
        invalid = changed | {"invoices.csv": "invoice_id\n"}
        assert client.post("/api/upload", files=multipart(invalid)).status_code == 422
        assert ask(client, new)[0] == new  # rejected input preserves AI history too
        client.post("/api/reset").raise_for_status()
        reset, text = ask(client, new)
        assert reset != new and "$52,900" in text


def test_simultaneous_streams_and_tool_threads_use_their_own_books(
    monkeypatch, changed
):
    from threading import Barrier

    barrier = Barrier(2)
    monkeypatch.setattr(streaming, "build_cfo_agent", lambda **kw: BooksAgent(barrier))
    app = create_app()
    with TestClient(app) as first, TestClient(app) as second:
        first.post("/api/upload", files=multipart(changed)).raise_for_status()
        with ThreadPoolExecutor(2) as pool:
            uploaded = pool.submit(ask, first)
            sample = pool.submit(ask, second)
            assert "$53,140" in uploaded.result(timeout=10)[1]
            assert "$52,900" in sample.result(timeout=10)[1]
        assert ft.monthly_summary("2026-09")["expenses"] == 52900


def test_missing_credentials_leave_finance_working_and_finish_error_streams(
    monkeypatch,
):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(config, "MODEL_PROVIDER", "anthropic")
    with TestClient(create_app()) as client:
        report = client.get("/api/report").json()
        assert report["agent_status"]["available"] is False
        assert report["monthly_summary"]["profit"] == -7830
        chat = sse(client.post("/api/ask", json={"question": "Why did profit drop?"}))
        assert chat[0]["type"] == "error" and "ANTHROPIC_API_KEY" in chat[0]["message"]
        assert chat[-1] == {"type": "done"}
        narrative = sse(client.get("/api/report/narrative"))
        assert "ANTHROPIC_API_KEY" in narrative[0]["error"]
        assert narrative[-1] == {"done": True}


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/report/narrative?month=bad", None),
        ("/api/ask", {"question": "hi", "month": "2026-07"}),
        ("/api/ask", {"question": " "}),
        ("/api/ask", {"question": "x" * 4001}),
    ],
)
def test_agent_request_validation_matches_the_report(path, body):
    with TestClient(create_app()) as client:
        response = client.get(path) if body is None else client.post(path, json=body)
        assert response.status_code == 422
