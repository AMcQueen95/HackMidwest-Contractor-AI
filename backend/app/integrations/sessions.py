"""What each browser has imported so far, so separate imports add up to one set of books."""

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock

from backend.app.integrations.records import BusinessFacts, Records


@dataclass
class ImportState:
    sources: dict[str, Records] = field(default_factory=dict)  # file name or bank item -> records
    plaid_items: dict[str, str] = field(default_factory=dict)  # item id -> access token (server only)
    facts: BusinessFacts = field(default_factory=BusinessFacts)

    def combined(self) -> Records:
        out = Records()
        for records in self.sources.values():
            out.extend(records)
        return out


class ImportStore:
    def __init__(self, max_sessions: int = 16, ttl_seconds: int = 3600):
        self._states: OrderedDict[str, tuple[ImportState, float]] = OrderedDict()
        self._lock, self.max_sessions, self.ttl = Lock(), max_sessions, ttl_seconds

    def get(self, token: str) -> ImportState:
        with self._lock:
            now = time.monotonic()
            for key, (_, expires) in list(self._states.items()):
                if expires <= now:
                    del self._states[key]
            state = self._states.get(token, (ImportState(), 0))[0]
            self._states[token] = (state, now + self.ttl)
            self._states.move_to_end(token)
            while len(self._states) > self.max_sessions:
                self._states.popitem(last=False)
            return state

    def clear(self, token: str) -> None:
        with self._lock:
            self._states.pop(token, None)
