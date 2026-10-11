"""Trade endpoints: list trades, pick one (Tyler's onboarding), load a trade's sample shop."""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from backend.app import trades as registry
from backend.app.config import agent_status
from backend.app.data import load_books
from backend.app.finance import build_report
from backend.app.trades.store import trades


class TradeRequest(BaseModel):
    trade: str | None  # e.g. "hvac"; null clears it
    load_sample: bool = False  # also replace the books with that trade's sample business


def trade_payload(books, month: str, token: str | None) -> dict:
    """The trade fields added to every report."""
    key = trades.get(token)
    trade = registry.get(key)
    if trade is None:
        return {"trade": None, "trade_sections": [], "suggested_questions": []}
    return {"trade": {"key": trade.KEY, "name": trade.NAME}, "trade_sections": trade.sections(books, month),
            "suggested_questions": trade.QUESTIONS}


def build_router(datasets, cookie_name: str, set_cookie: Callable) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/trades")
    def list_trades():
        return {"trades": registry.catalog()}

    @router.get("/trade")
    def get_trade(request: Request):
        trade = registry.get(trades.get(request.cookies.get(cookie_name)))
        return {"trade": {"key": trade.KEY, "name": trade.NAME, "questions": trade.QUESTIONS} if trade else None}

    @router.post("/trade")
    def set_trade(request: Request, response: Response, body: TradeRequest):
        if body.trade is not None and registry.get(body.trade) is None:
            known = ", ".join(registry.TRADES)
            raise HTTPException(422, f"Unknown or not-yet-available trade '{body.trade}'. Available: {known}.")
        token, dataset = datasets.ensure(request.cookies.get(cookie_name))
        if body.load_sample:
            if body.trade not in registry.SAMPLES:
                raise HTTPException(422, "That trade has no sample business.")
            token, dataset = datasets.replace(load_books(registry.SAMPLES[body.trade]), token, is_sample=True)
        trades.set(token, body.trade)
        dataset.agent_state.sessions.clear()  # advice and analysts change with the trade
        dataset.agent_state.narratives.clear()
        set_cookie(request, response, token)
        report = build_report(dataset.books, is_sample=dataset.is_sample, dataset_revision=dataset.revision)
        return report | trade_payload(dataset.books, report["month"], token) | {"agent_status": agent_status()}

    return router
