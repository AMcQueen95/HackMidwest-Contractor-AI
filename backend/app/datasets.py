"""Bounded, temporary browser datasets. One process; no disk persistence."""

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

from .data import Books


@dataclass(frozen=True)
class Dataset:
    books: Books
    is_sample: bool
    revision: str


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

    def replace(self, books: Books, token: str | None) -> tuple[str, Dataset]:
        with self._lock:
            self._expire()
            token = token if token in self._sessions else secrets.token_urlsafe(24)
            dataset = Dataset(books, False, secrets.token_hex(12))
            self._sessions[token] = (dataset, time.monotonic() + self.ttl_seconds)
            self._sessions.move_to_end(token)
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)
            return token, dataset

    def reset(self, token: str | None):
        with self._lock:
            self._sessions.pop(token, None)
