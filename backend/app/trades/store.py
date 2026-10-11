"""The kinds of work each company (or, without accounts, each browser) does.

Signed in, the choice is saved in the company's encrypted workspace with its books,
apart from the books themselves, so it survives new uploads and imports.
A profile is {"trades": ["hvac", ...], "other": str | None, "done": bool}; "done"
means the owner answered the onboarding question.
"""

import time
from collections import OrderedDict
from threading import Lock

from backend.app.accounts.context import active_workspace

EMPTY = {"trades": [], "other": None, "done": False}


class TradeStore:
    def __init__(self, max_sessions: int = 64, ttl_seconds: int = 3600):
        self._profiles: OrderedDict[str, tuple[dict, float]] = OrderedDict()
        self._lock, self.max_sessions, self.ttl = Lock(), max_sessions, ttl_seconds

    def profile(self, token: str | None) -> dict:
        if workspace := active_workspace.get():
            data = workspace.data
            trades = data.get("trades") or ([data["trade"]] if data.get("trade") else [])
            return {"trades": list(trades), "other": data.get("trade_other"),
                    "done": bool(data.get("trade_done") or trades)}
        with self._lock:
            entry = self._profiles.get(token or "")
            if entry is None or entry[1] <= time.monotonic():
                return dict(EMPTY)
            self._profiles[token] = (entry[0], time.monotonic() + self.ttl)
            return dict(entry[0])

    def get(self, token: str | None) -> list[str]:
        """The selected trade keys."""
        return self.profile(token)["trades"]

    def set(self, token: str, trades: list[str], other: str | None = None) -> None:
        profile = {"trades": list(trades), "other": (other or "").strip() or None, "done": True}
        if workspace := active_workspace.get():
            data = workspace.data
            data.pop("trade", None)  # older single-trade field
            data["trades"], data["trade_done"] = profile["trades"], True
            if profile["other"]:
                data["trade_other"] = profile["other"]
            else:
                data.pop("trade_other", None)
            return
        with self._lock:
            self._profiles[token] = (profile, time.monotonic() + self.ttl)
            self._profiles.move_to_end(token)
            while len(self._profiles) > self.max_sessions:
                self._profiles.popitem(last=False)


trades = TradeStore()
