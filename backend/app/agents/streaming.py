"""Streamed answers for the API, in the event shapes the frontend reads.

ask_stream() yields chat events for POST /api/ask:
    {"type": "session", "session_id": ...}   first
    {"type": "status", "text": "Consulted the cash flow analyst"}
    {"type": "text", "text": <chunk>}
    {"type": "text_reset"}                    drop text so far (a preamble before a tool call)
    {"type": "card", "card": {"type": <finance function>, "data": <its result>}}
    {"type": "error", "message": ...}
    {"type": "done"}

stream_narrative() yields text chunks of the month's report in the plain-text
format the frontend parses: a summary, then "Issues" and "Recommendations"
headings, each followed by "- " bullets. It yields None to mean "discard the
text so far" (a preamble the model wrote before calling a tool).
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import date

from backend.app.agents import finance_tools as ft
from backend.app.agents.cfo_agent import _sessions, build_cfo_agent
from backend.app.agents.events import set_emitter
from backend.app.agents.prompts import STE_RULES
from backend.app.agent_context import active_agent_state

log = logging.getLogger(__name__)

_narratives: dict[str, str] = {}  # month -> finished report text for the current books


def _histories():
    state = active_agent_state.get()
    return (state.sessions, state.narratives) if state is not None else (_sessions, _narratives)


def reset_caches() -> None:
    """Forget cached reports and conversations, e.g. after new books are uploaded."""
    sessions, narratives = _histories()
    narratives.clear()
    sessions.clear()


def _month_name(month: str) -> str:
    return date.fromisoformat(f"{month}-01").strftime("%B %Y")


def _narrative_prompt(month: str) -> str:
    return f"""\
Write the {_month_name(month)} report for the owner. Consult every analyst first.

Then write plain text only: no markdown, no bold, no headings with #, no tables.
Use exactly this layout:

<Two or three sentences on how the month went and the main reasons why.>

Issues
- <one problem with its numbers>
<three to five issues, biggest dollar impact first>

Recommendations
- <one action, starting with a verb, and what it's worth>
<three or four recommendations, most valuable first>

The words Issues and Recommendations must each be alone on their own line.

{STE_RULES}"""


def _seed_messages(month: str | None) -> list | None:
    """Start a chat with the month's report already in the history, so the owner
    can ask about it ("tell me more about the second issue")."""
    text = _histories()[1].get(month or "")
    if not text:
        return None
    return [{"role": "user", "content": [{"text": f"Give me the {_month_name(month)} report."}]},
            {"role": "assistant", "content": [{"text": text}]}]


async def _run(agent, prompt: str) -> AsyncIterator[dict]:
    """Run an agent and yield text, status and card events as they happen."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    put = lambda event: loop.call_soon_threadsafe(queue.put_nowait, event)  # noqa: E731

    async def produce():
        set_emitter(put)  # copied into the tool threads this task starts
        text_since_tool = False
        try:
            async for event in agent.stream_async(prompt):
                if "current_tool_use" in event and text_since_tool:
                    put({"type": "text_reset"})
                    text_since_tool = False
                elif event.get("data"):
                    put({"type": "text", "text": event["data"]})
                    text_since_tool = True
        except Exception as e:  # noqa: BLE001 - report any failure to the client
            log.exception("Agent run failed")
            put({"type": "error", "message": str(e)})
        finally:
            put(None)

    task = asyncio.create_task(produce())
    try:
        while (event := await queue.get()) is not None:
            yield event
    finally:
        task.cancel()


async def ask_stream(question: str, session_id: str | None = None,
                     month: str | None = None) -> AsyncIterator[dict]:
    """Answer an owner's question as a stream of chat events."""
    sessions, _ = _histories()
    # A session ID from another dataset/browser must not select its conversation.
    session_id = session_id if session_id in sessions else uuid.uuid4().hex
    if session_id not in sessions:
        agent = build_cfo_agent(messages=_seed_messages(month))
        if len(sessions) >= 32:
            del sessions[next(iter(sessions))]
        sessions[session_id] = agent
    yield {"type": "session", "session_id": session_id}

    seen_cards = set()
    async for event in _run(sessions[session_id], question):
        if event["type"] == "card":  # one card per finance function per answer
            if event["card"]["type"] in seen_cards:
                continue
            seen_cards.add(event["card"]["type"])
        yield event
    yield {"type": "done"}


async def stream_narrative(month: str | None = None) -> AsyncIterator[str | None]:
    """The month's report as streamed text. Cached per month until the books change."""
    month = month or ft.latest_full_month(ft.get_books())
    _, narratives = _histories()
    if month in narratives:
        text = narratives[month]
        for i in range(0, len(text), 24):  # replay quickly so the UI still animates
            yield text[i:i + 24]
            await asyncio.sleep(0.01)
        return

    parts: list[str] = []
    async for event in _run(build_cfo_agent(), _narrative_prompt(month)):
        if event["type"] == "text":
            parts.append(event["text"])
            yield event["text"]
        elif event["type"] == "text_reset":
            parts.clear()
            yield None
        elif event["type"] == "error":
            raise RuntimeError(event["message"])
    narratives[month] = "".join(parts).strip()
