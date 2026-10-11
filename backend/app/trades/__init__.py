"""Trade profiles: sections, agent advice and suggested questions for each kind of contractor.

A trade module (hvac.py) provides KEY, NAME, SECTIONS, sections(books, through_month),
ADVICE (for the agents' prompts), QUESTIONS (chat suggestions), CATEGORY_HINTS (for
categorizing imports) and estimate_job_type (for jobs inferred from bank payments).
A company can do several trades, and can describe other work in its own words.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from backend.app.trades import electrical, hvac, plumbing

TRADES = {t.KEY: t for t in (hvac, plumbing, electrical)}
PLANNED: dict[str, str] = {}
SAMPLES = {key: Path(__file__).parent / "samples" / key for key in TRADES}

active_trades: ContextVar[tuple[list[str], str | None]] = ContextVar("active_trades", default=([], None))


def get(key: str | None):
    return TRADES.get(key or "")


def selected(keys) -> list:
    """Trade modules for a list of keys (or one key), in a stable order, unknown keys dropped."""
    keys = [keys] if isinstance(keys, str) else list(keys or [])
    return [t for k, t in TRADES.items() if k in keys]


def current_all() -> list:
    """The trade modules for the request being handled."""
    return selected(active_trades.get()[0])


def current():
    """The first selected trade, if any (for code that needs just one)."""
    trades = current_all()
    return trades[0] if trades else None


def current_other() -> str | None:
    """Other work the owner described in their own words."""
    return active_trades.get()[1]


@contextmanager
def use_trade(keys, other: str | None = None):
    keys = [keys] if isinstance(keys, str) else list(keys or [])
    token = active_trades.set(([k for k in keys if k in TRADES], other))
    try:
        yield
    finally:
        active_trades.reset(token)


def names(trades) -> str:
    """'HVAC', 'HVAC and Plumbing', 'HVAC, Plumbing and Electrical'."""
    labels = [t.NAME for t in trades]
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]


def catalog() -> list[dict]:
    ready = [{"key": t.KEY, "name": t.NAME, "ready": True, "has_sample": t.KEY in SAMPLES,
              "sections": [s.__name__ for s in t.SECTIONS], "questions": t.QUESTIONS} for t in TRADES.values()]
    return ready + [{"key": k, "name": v, "ready": False} for k, v in PLANNED.items()]
