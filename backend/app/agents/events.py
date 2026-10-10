"""Side channel from inside tools to a streamed answer.

Tools run in worker threads (Strands uses asyncio.to_thread), which copy the
caller's context, so a ContextVar set by the streaming code reaches them.
Outside a streamed answer (CLI, tests) emit() does nothing.
"""

from collections.abc import Callable
from contextvars import ContextVar

_emitter: ContextVar[Callable[[dict], None] | None] = ContextVar("agent_event_emitter", default=None)


def emit(event: dict) -> None:
    send = _emitter.get()
    if send is not None:
        send(event)


def set_emitter(send: Callable[[dict], None] | None):
    return _emitter.set(send)
