"""Request-local books and per-dataset AI history, shared across tool threads."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from .data import Books


@dataclass
class AgentState:
    sessions: dict = field(default_factory=dict)
    narratives: dict[str, str] = field(default_factory=dict)


active_books: ContextVar[Books | None] = ContextVar("active_books", default=None)
active_agent_state: ContextVar[AgentState | None] = ContextVar(
    "active_agent_state", default=None
)


@contextmanager
def use_dataset(books: Books, state: AgentState):
    books_token = active_books.set(books)
    state_token = active_agent_state.set(state)
    try:
        yield
    finally:
        active_agent_state.reset(state_token)
        active_books.reset(books_token)
