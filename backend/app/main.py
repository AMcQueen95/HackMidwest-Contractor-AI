"""Live finance API. Start with: python -m uvicorn backend.app.main:app."""

import json
import os
from pathlib import Path
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .data import Books, BooksValidationError, load_books, load_books_from_uploads
from .data.loader import COLUMNS, MAX_FILE_BYTES
from .finance import affordability, build_report
from .agent_context import use_dataset
from .agents import streaming
from .config import agent_status
from .integrations.routes import build_router
from .trades import use_trade
from .trades import routes as trade_routes
from .trades.store import trades
from .accounts.provider import SupabaseBackend
from .accounts.routes import build_auth_router, user_from
from .accounts.context import active_workspace
from .accounts.storage import AccountDatasetStore, load_workspace, save_workspace, snapshot, cipher

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
    sample_books: Books | None = None, *, frontend_directory: Path | None = None,
    auth_backend=None,
) -> FastAPI:
    app = FastAPI(title="Toolbelt CFO finance API")
    store = AccountDatasetStore(sample_books if sample_books is not None else load_books())
    app.state.datasets = store
    provider = auth_backend if auth_backend is not None else SupabaseBackend()
    app.state.accounts = provider

    @app.middleware("http")
    async def protect_accounts(request: Request, call_next):
        path = request.url.path
        # Same-origin cookie authentication: block browser cross-origin mutations.
        if path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            allowed = {str(request.base_url).rstrip("/")}
            if site := os.getenv("PUBLIC_APP_URL"):
                parsed = urlsplit(site)
                allowed.add(f"{parsed.scheme}://{parsed.netloc}")
            if origin and origin not in allowed:
                return JSONResponse(status_code=403, content={"detail": "This request must come from the app."})
        public = path in {"/api/health", "/api/demo/report", "/api/demo/affordability"}
        account_route = path.startswith("/api/auth/") or path == "/api/companies"
        if not path.startswith("/api/") or public or account_route:
            response = await call_next(request)
            if account_route:
                response.headers["Cache-Control"] = "no-store"
            return response
        context_token = None
        try:
            token, user = await run_in_threadpool(user_from, request, provider)
            company_id = request.headers.get("x-company-id")
            if not company_id:
                raise HTTPException(409, "Choose or create a company first.")
            workspace = await run_in_threadpool(load_workspace, provider, store, token, user, company_id)
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                await run_in_threadpool(cipher)  # Fail before imports/bank calls if storage is unavailable.
            original = snapshot(workspace)
            request.state.user = user
            request.state.company = workspace.company
            context_token = active_workspace.set(workspace)
            response = await call_next(request)
            if response.status_code < 400:
                await run_in_threadpool(save_workspace, provider, workspace, original)
            response.headers["Cache-Control"] = "no-store"
            return response
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail},
                                headers={"Cache-Control": "no-store"})
        finally:
            if context_token is not None:
                active_workspace.reset(context_token)

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

    @app.get("/api/demo/report")
    def demo_report(month: str | None = None):
        return build_report(store.sample.books, month, is_sample=True, dataset_revision="sample") | {
            "has_books": True, "agent_status": {"available": False,
            "message": "Sign in to use AI analysis with your own company."}}

    @app.get("/api/demo/affordability")
    def demo_affordability(amount: str):
        return affordability(store.sample.books, amount)

    def empty_report():
        return {"has_books": False, "company": active_workspace.get().company,
                "agent_status": agent_status(),
                "trade_setup": trade_routes.trade_payload(None, None, None)["trade_setup"]}

    @app.get("/api/report")
    def report(request: Request, response: Response, month: str | None = None):
        if active_workspace.get().dataset is None:
            return empty_report()
        token, dataset = store.ensure(request.cookies.get(COOKIE_NAME))
        _set_cookie(request, response, token)
        report = build_report(
            dataset.books,
            month,
            is_sample=dataset.is_sample,
            dataset_revision=dataset.revision,
        )
        return report | trade_routes.trade_payload(dataset.books, report["month"], token) | {
            "agent_status": agent_status(), "has_books": True, "company": request.state.company}

    @app.get("/api/report/narrative")
    def narrative(request: Request, month: str | None = None):
        store.get(None)  # Empty companies cannot analyze the sample dataset.
        token, dataset = store.ensure(request.cookies.get(COOKIE_NAME))
        selected = build_report(dataset.books, month)["month"]

        async def events():
            with use_dataset(dataset.books, dataset.agent_state), use_trade(trades.get(token), trades.profile(token)["other"]):
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
        store.get(None)
        token, dataset = store.ensure(request.cookies.get(COOKIE_NAME))
        selected = build_report(dataset.books, body.month)["month"]

        async def events():
            with use_dataset(dataset.books, dataset.agent_state), use_trade(trades.get(token), trades.profile(token)["other"]):
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
            return candidate_report | trade_routes.trade_payload(
                books, candidate_report["month"], token
            ) | {
                "is_sample": False,
                "dataset_revision": dataset.revision,
                "agent_status": agent_status(),
                "has_books": True,
                "company": request.state.company,
            }
        finally:
            for file in files:
                await file.close()

    @app.post("/api/reset")
    def reset(request: Request, response: Response):
        store.reset(request.cookies.get(COOKIE_NAME))
        response.delete_cookie(COOKIE_NAME)
        return empty_report()

    app.include_router(build_auth_router(provider))
    app.include_router(build_router(store, COOKIE_NAME, _set_cookie))
    app.include_router(trade_routes.build_router(store, COOKIE_NAME, _set_cookie))

    directory = frontend_directory if frontend_directory is not None else FRONTEND_DIST
    if directory.is_dir():
        app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
    return app


app = create_app()
