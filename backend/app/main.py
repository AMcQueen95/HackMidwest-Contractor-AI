"""Toolbelt CFO API: serves the report data, the agents and the built frontend.

    uvicorn backend.app.main:app --reload --port 8000

Streaming endpoints send server-sent events: one `data: <json>` line per event.
"""

import json
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.app import finance
from backend.app.agents import ask_stream, reset_caches, stream_narrative
from backend.app.agents import finance_tools as ft
from backend.app.data import BooksValidationError, load_books_from_uploads

app = FastAPI(title="Toolbelt CFO")

UPLOAD_FILES = ("transactions.csv", "jobs.csv", "invoices.csv", "business.json")
_state = {"is_sample": True}


def _months() -> list[str]:
    """Every month from the books' opening date through the latest full month."""
    books = ft.get_books()
    start = date.fromisoformat(books.business["opening_balance_date"]).replace(day=1)
    end = ft.latest_full_month(books)
    months, current = [], start
    while (m := current.strftime("%Y-%m")) <= end:
        months.append(m)
        current = (current.replace(day=28) + (date.resolution * 4)).replace(day=1)
    return months


def _pick_month(month: str | None) -> str:
    months = _months()
    return month if month in months else months[-1]


def _sse(events: AsyncIterator[dict]) -> StreamingResponse:
    async def body():
        async for event in events:
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- Report -----------------------------------------------------------------------

@app.get("/api/report")
def get_report(month: str | None = None) -> dict:
    """Everything the report page shows for one month, straight from the finance functions."""
    books, months = ft.get_books(), _months()
    month = _pick_month(month)
    previous = months[months.index(month) - 1] if months.index(month) > 0 else None
    return {
        "business": books.business,
        "monthly_summary": finance.monthly_summary(books, month),
        "expense_changes": finance.expense_changes(books, month),
        "recurring_charges": finance.recurring_charges(books, month),
        "job_profitability": finance.job_profitability(books, month),
        "losing_jobs": finance.losing_jobs(books, month),
        "margin_by_job_type": finance.margin_by_job_type(books, month),
        "cash_balance": finance.cash_balance(books),
        "receivables": finance.receivables(books),
        "month": month,
        "months": months,
        "is_sample": _state["is_sample"],
        "previous_summary": finance.monthly_summary(books, previous) if previous else None,
        "narrative": None,
    }


@app.get("/api/report/narrative")
def get_narrative(month: str | None = None) -> StreamingResponse:
    """The CFO's written report, streamed as {"text": chunk} events. {"reset": true}
    means discard the text so far."""
    month = _pick_month(month)

    async def events():
        try:
            async for chunk in stream_narrative(month):
                yield {"reset": True} if chunk is None else {"text": chunk}
            yield {"done": True}
        except Exception as e:  # noqa: BLE001 - show the problem instead of hanging
            yield {"error": str(e)}

    return _sse(events())


@app.get("/api/affordability")
def get_affordability(amount: float = Query(gt=0)) -> dict:
    return finance.affordability(ft.get_books(), amount)


# --- Chat -------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    session_id: str | None = None
    month: str | None = None  # seeds a new conversation with that month's report


@app.post("/api/ask")
def post_ask(body: AskRequest) -> StreamingResponse:
    """Stream the CFO's answer: session, status, text, card, error and done events."""
    if not body.question.strip():
        raise HTTPException(422, "Ask a question first.")
    return _sse(ask_stream(body.question.strip(), body.session_id, body.month))


# --- Upload -----------------------------------------------------------------------

@app.post("/api/upload")
async def post_upload(files: list[UploadFile]) -> dict:
    """Replace the books with four uploaded files. Nothing changes unless all four validate."""
    uploads = {f.filename: await f.read() for f in files}
    missing = [name for name in UPLOAD_FILES if name not in uploads]
    if missing:
        raise HTTPException(422, f"Missing files: {', '.join(missing)}")
    try:
        books = load_books_from_uploads({name: uploads[name] for name in UPLOAD_FILES})
    except BooksValidationError as e:
        raise HTTPException(422, str(e)) from e
    ft.use_books(books)
    reset_caches()
    _state["is_sample"] = False
    return {"ok": True, "business": books.business["name"], "months": _months()}


# --- Frontend ---------------------------------------------------------------------

_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.is_dir():  # after `npm run build`; in development Vite serves the UI on :5173
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
