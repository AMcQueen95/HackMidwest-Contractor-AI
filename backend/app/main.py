"""Live finance API. Start with: python -m uvicorn backend.app.main:app."""

import json
from pathlib import Path
from collections.abc import AsyncIterator

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .data import Books, BooksValidationError, load_books, load_books_from_uploads
from .data.loader import COLUMNS, MAX_FILE_BYTES
from .datasets import DatasetStore
from .finance import affordability, build_report
from .agent_context import use_dataset
from .agents import streaming
from .config import agent_status

COOKIE_NAME = "toolbelt_session"
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=128)
    month: str | None = None


def _sse(events: AsyncIterator[dict]) -> StreamingResponse:
    async def body():
        async for event in events:
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _set_cookie(request: Request, response: Response, token: str):
    if request.cookies.get(COOKIE_NAME) != token:
        response.set_cookie(
            COOKIE_NAME,
            token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )


def create_app(
    sample_books: Books | None = None, *, frontend_directory: Path | None = None
) -> FastAPI:
    app = FastAPI(title="Toolbelt CFO finance API")
    store = DatasetStore(sample_books if sample_books is not None else load_books())
    app.state.datasets = store

    @app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        if request.url.path == "/api/upload":
            length = request.headers.get("content-length")
            if length and (
                not length.isdigit() or int(length) > 4 * MAX_FILE_BYTES + 65536
            ):
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": "Upload exceeds the four-file size limit (10 MiB per file)"
                    },
                )
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def validation_error(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/report")
    def report(request: Request, response: Response, month: str | None = None):
        token, dataset = store.ensure(request.cookies.get(COOKIE_NAME))
        _set_cookie(request, response, token)
        return build_report(
            dataset.books,
            month,
            is_sample=dataset.is_sample,
            dataset_revision=dataset.revision,
        ) | {"agent_status": agent_status()}

    @app.get("/api/report/narrative")
    def narrative(request: Request, month: str | None = None):
        token, dataset = store.ensure(request.cookies.get(COOKIE_NAME))
        selected = build_report(dataset.books, month)["month"]

        async def events():
            with use_dataset(dataset.books, dataset.agent_state):
                try:
                    async for chunk in streaming.stream_narrative(selected):
                        yield {"reset": True} if chunk is None else {"text": chunk}
                except Exception as exc:
                    yield {"error": str(exc)}
                yield {"done": True}

        response = _sse(events())
        _set_cookie(request, response, token)
        return response

    @app.post("/api/ask")
    def ask(request: Request, body: AskRequest):
        if not body.question.strip():
            raise HTTPException(422, "Ask a question first.")
        token, dataset = store.ensure(request.cookies.get(COOKIE_NAME))
        selected = build_report(dataset.books, body.month)["month"]

        async def events():
            with use_dataset(dataset.books, dataset.agent_state):
                try:
                    async for event in streaming.ask_stream(
                        body.question.strip(), body.session_id, selected
                    ):
                        yield event
                except Exception as exc:
                    yield {"type": "error", "message": str(exc)}
                    yield {"type": "done"}

        response = _sse(events())
        _set_cookie(request, response, token)
        return response

    @app.get("/api/affordability")
    def purchase_check(request: Request, amount: str):
        return affordability(store.get(request.cookies.get(COOKIE_NAME)).books, amount)

    @app.post("/api/upload")
    async def upload(
        request: Request, response: Response, files: list[UploadFile] = File(...)
    ):
        required = set(COLUMNS) | {"business.json"}
        names = [file.filename for file in files]
        try:
            if len(files) != 4 or set(names) != required:
                raise BooksValidationError(
                    "Select exactly transactions.csv, jobs.csv, invoices.csv, and business.json, with no duplicates"
                )
            contents = {}
            for file in files:
                contents[file.filename] = await file.read(MAX_FILE_BYTES + 1)
                if len(contents[file.filename]) > MAX_FILE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"{file.filename}: exceeds the 10 MiB size limit",
                    )
            # Validate both the input and complete report before committing state.
            books = await run_in_threadpool(load_books_from_uploads, contents)
            candidate_report = await run_in_threadpool(build_report, books)
            token, dataset = store.replace(books, request.cookies.get(COOKIE_NAME))
            response.set_cookie(
                COOKIE_NAME,
                token,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            return candidate_report | {
                "is_sample": False,
                "dataset_revision": dataset.revision,
                "agent_status": agent_status(),
            }
        finally:
            for file in files:
                await file.close()

    @app.post("/api/reset")
    def reset(request: Request, response: Response):
        store.reset(request.cookies.get(COOKIE_NAME))
        response.delete_cookie(COOKIE_NAME)
        return build_report(
            store.sample.books, is_sample=True, dataset_revision="sample"
        ) | {"agent_status": agent_status()}

    directory = frontend_directory if frontend_directory is not None else FRONTEND_DIST
    if directory.is_dir():
        app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
    return app


app = create_app()
