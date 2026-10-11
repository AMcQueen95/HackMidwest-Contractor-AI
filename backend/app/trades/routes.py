"""Trade endpoints: list trades, save the company's kinds of work (onboarding), load a sample."""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.app import trades as registry
from backend.app.accounts.context import active_workspace
from backend.app.config import agent_status
from backend.app.data import load_books
from backend.app.finance import build_report
from backend.app.trades import common
from backend.app.trades.store import trades


class TradeRequest(BaseModel):
    trades: list[str] | None = None  # any of "hvac", "plumbing", "electrical"
    trade: str | None = None  # one trade (older clients)
    other: str | None = Field(None, max_length=200)  # other work, in the owner's words
    load_sample: bool = False  # with exactly one trade: replace the books with its sample business


def trade_payload(books, month: str | None, token: str | None) -> dict:
    """The trade fields added to every report."""
    profile = trades.profile(token)
    chosen = registry.selected(profile["trades"])
    setup = profile | {"names": [t.NAME for t in chosen]}
    if not chosen:
        return {"trade": None, "trades": [], "trade_sections": [], "suggested_questions": [], "trade_setup": setup}
    sections = []
    with common.several_trades(len(chosen) > 1):
        for trade in chosen:
            for section in (trade.sections(books, month) if books is not None and month else []):
                if section["status"] != "ok":
                    continue  # nothing to show from this company's data (the agents still see why)
                sections.append(section | {"trade": trade.KEY, "trade_name": trade.NAME})
    questions = [q for group in zip(*(t.QUESTIONS for t in chosen)) for q in group][:6]
    return {"trade": {"key": chosen[0].KEY, "name": registry.names(chosen)},
            "trades": [{"key": t.KEY, "name": t.NAME} for t in chosen], "trade_sections": sections,
            "suggested_questions": questions, "trade_setup": setup}


def build_router(datasets, cookie_name: str, set_cookie: Callable) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/trades")
    def list_trades():
        return {"trades": registry.catalog()}

    @router.get("/trade")
    def get_trade(request: Request):
        return trade_payload(None, None, request.cookies.get(cookie_name))["trade_setup"]

    @router.post("/trade")
    def set_trade(request: Request, response: Response, body: TradeRequest):
        keys = body.trades if body.trades is not None else ([body.trade] if body.trade else [])
        unknown = [k for k in keys if registry.get(k) is None]
        if unknown:
            raise HTTPException(422, f"Unknown trade: {', '.join(unknown)}. Choose from {', '.join(registry.TRADES)}.")
        if body.trades is not None and not keys and not (body.other or "").strip():
            raise HTTPException(422, "Choose at least one kind of work, or describe yours under Other.")
        token, dataset = datasets.ensure(request.cookies.get(cookie_name))
        if body.load_sample:
            if len(keys) != 1:
                raise HTTPException(422, "Choose exactly one trade to load its sample business.")
            token, dataset = datasets.replace(load_books(registry.SAMPLES[keys[0]]), token, is_sample=True)
        trades.set(token, keys, body.other)
        set_cookie(request, response, token)
        workspace = active_workspace.get()
        if workspace is not None and workspace.dataset is None:  # a new company: no books yet
            return {"has_books": False, "company": workspace.company} | trade_payload(None, None, token)
        dataset.agent_state.sessions.clear()  # advice and analysts change with the trades
        dataset.agent_state.narratives.clear()
        report = build_report(dataset.books, is_sample=dataset.is_sample, dataset_revision=dataset.revision)
        return report | trade_payload(dataset.books, report["month"], token) | {"agent_status": agent_status()}

    return router
