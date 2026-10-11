"""Trade profiles: sections, agent advice and suggested questions for each kind of contractor.

A trade module (hvac.py) provides KEY, NAME, sections(books, through_month),
ADVICE (for the agents' prompts), QUESTIONS (chat suggestions) and
CATEGORY_HINTS (for categorizing imported transactions).
"""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from backend.app.trades import electrical, hvac, plumbing

TRADES = {t.KEY: t for t in (hvac, plumbing, electrical)}
PLANNED: dict[str, str] = {}
SAMPLES = {key: Path(__file__).parent / "samples" / key for key in TRADES}

active_trade: ContextVar[str | None] = ContextVar("active_trade", default=None)


def get(key: str | None):
    return TRADES.get(key or "")


def current():
    """The trade module for the request being handled, if the owner picked one."""
    return get(active_trade.get())


@contextmanager
def use_trade(key: str | None):
    token = active_trade.set(key if key in TRADES else None)
    try:
        yield
    finally:
        active_trade.reset(token)


def catalog() -> list[dict]:
    ready = [{"key": t.KEY, "name": t.NAME, "ready": True, "has_sample": t.KEY in SAMPLES,
              "sections": [s.__name__ for s in t.SECTIONS], "questions": t.QUESTIONS} for t in TRADES.values()]
    return ready + [{"key": k, "name": v, "ready": False} for k, v in PLANNED.items()]
