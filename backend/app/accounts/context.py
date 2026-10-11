"""Authorized workspace for one request; copied into finance/import worker threads."""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


@dataclass
class Workspace:
    user_id: str
    company: dict
    token: str
    data: dict
    database_revision: str | None
    dataset: Any
    imports: Any


active_workspace: ContextVar[Workspace | None] = ContextVar("active_workspace", default=None)
