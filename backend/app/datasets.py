"""Bounded, temporary browser datasets. One process; no disk persistence."""

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock

from .data import Books
from .agent_context import AgentState


@dataclass(frozen=True)
class Dataset:
    books: Books
    is_sample: bool
    revision: str
    agent_state: AgentState = field(default_factory=AgentState)


class DatasetStore:
    def __init__(self, sample: Books, *, max_sessions=16, ttl_seconds=3600):
        self.sample = Dataset(sample, True, "sample")
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._sessions = OrderedDict()
        self._lock = Lock()

    def _expire(self):
        now = time.monotonic()
        for token, (_, expires) in list(self._sessions.items()):
            if expires <= now:
                del self._sessions[token]

    def get(self, token: str | None) -> Dataset:
        with self._lock:
            self._expire()
            if token not in self._sessions:
                return self.sample
            dataset, _ = self._sessions[token]
            self._sessions[token] = (dataset, time.monotonic() + self.ttl_seconds)
            self._sessions.move_to_end(token)
            return dataset

    def ensure(self, token: str | None) -> tuple[str, Dataset]:
        """Give even sample-book browsers their own AI conversation/cache state."""
        with self._lock:
            self._expire()
            if token in self._sessions:
                dataset, _ = self._sessions[token]
            else:
                token = secrets.token_urlsafe(24)
                dataset = Dataset(self.sample.books, True, "sample")
            self._sessions[token] = (dataset, time.monotonic() + self.ttl_seconds)
            self._sessions.move_to_end(token)
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)
            return token, dataset

    def replace(self, books: Books, token: str | None, *, is_sample: bool = False) -> tuple[str, Dataset]:
        with self._lock:
            self._expire()
            token = token if token in self._sessions else secrets.token_urlsafe(24)
            dataset = Dataset(books, is_sample, secrets.token_hex(12))
            self._sessions[token] = (dataset, time.monotonic() + self.ttl_seconds)
            self._sessions.move_to_end(token)
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)
            return token, dataset

    def reset(self, token: str | None):
        with self._lock:
            self._sessions.pop(token, None)
