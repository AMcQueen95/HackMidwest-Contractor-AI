"""Which trade each browser picked. Kept apart from the books, so it survives imports."""

import time
from collections import OrderedDict
from threading import Lock


class TradeStore:
    def __init__(self, max_sessions: int = 64, ttl_seconds: int = 3600):
        self._trades: OrderedDict[str, tuple[str | None, float]] = OrderedDict()
        self._lock, self.max_sessions, self.ttl = Lock(), max_sessions, ttl_seconds

    def get(self, token: str | None) -> str | None:
        with self._lock:
            entry = self._trades.get(token or "")
            if entry is None or entry[1] <= time.monotonic():
                return None
            self._trades[token] = (entry[0], time.monotonic() + self.ttl)
            return entry[0]

    def set(self, token: str, trade: str | None) -> None:
        with self._lock:
            self._trades[token] = (trade, time.monotonic() + self.ttl)
            self._trades.move_to_end(token)
            while len(self._trades) > self.max_sessions:
                self._trades.popitem(last=False)


trades = TradeStore()
