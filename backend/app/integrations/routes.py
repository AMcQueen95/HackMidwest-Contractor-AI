"""Import endpoints: any CSV exports, and bank connections through Plaid.

Each browser's imports add up: upload a bank export, then an invoice export,
then connect a card account, and every step rebuilds one set of books from all
of them. Nothing replaces the current books unless the whole result validates.
"""

import asyncio
import copy
from collections.abc import Callable

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from backend.app.config import agent_status
from backend.app.data.loader import MAX_FILE_BYTES
from backend.app.finance import build_report
from backend.app.integrations import plaid
from backend.app.integrations.ai import categorize
from backend.app.integrations.csv_import import read_file
from backend.app.integrations.records import BusinessFacts, assemble
from backend.app.integrations.sandbox_bank import contractor_config
from backend.app.integrations.sessions import ImportState, ImportStore

MAX_FILES = 20


class ExchangeRequest(BaseModel):
    public_token: str


class SandboxRequest(BaseModel):
    bank: str = "contractor"  # "contractor": realistic HVAC shop; "plaid": Plaid's generic sample data


def build_router(datasets, cookie_name: str, set_cookie: Callable) -> APIRouter:
    router = APIRouter(prefix="/api")
    imports = ImportStore()

    def session(request: Request) -> tuple[str, ImportState]:
        token, _ = datasets.ensure(request.cookies.get(cookie_name))
        return token, imports.get(token)

    def require_ai():
        if not agent_status()["available"]:
            raise HTTPException(503, "Reading imported files needs the AI. Add ANTHROPIC_API_KEY to backend/.env.")

    async def rebuild(request: Request, response: Response, token: str, state: ImportState,
                      sources: dict, dry_run: bool = False) -> dict:
        books, warnings, summary = await asyncio.to_thread(
            assemble, copy.deepcopy(ImportState(sources=sources).combined()), state.facts)
        report = await asyncio.to_thread(build_report, books)
        result = {"warnings": warnings, "summary": summary,
                  "sources": [{"name": n, "transactions": len(r.transactions), "invoices": len(r.invoices),
                               "jobs": len(r.jobs)} for n, r in sources.items()]}
        if dry_run:
            return result | {"applied": False}
        state.sources = sources
        token, dataset = datasets.replace(books, token)
        set_cookie(request, response, token)
        return result | {"applied": True, "report": report | {
            "is_sample": False, "dataset_revision": dataset.revision, "agent_status": agent_status()}}

    # --- Any CSVs -----------------------------------------------------------------

    @router.post("/import")
    async def import_files(
        request: Request, response: Response, files: list[UploadFile] = File(...),
        business_name: str | None = Form(None), opening_balance: float | None = Form(None),
        labor_rate: float | None = Form(None), tax_reserve_rate: float | None = Form(None),
        replace: bool = Form(False), dry_run: bool = Form(False),
    ):
        """Upload any number of CSV exports. Each is identified, converted and combined
        with what this browser imported before (replace=true starts over)."""
        require_ai()
        if not files or len(files) > MAX_FILES:
            raise HTTPException(422, f"Upload between 1 and {MAX_FILES} files.")
        token, state = session(request)
        contents = {}
        try:
            for f in files:
                data = await f.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES:
                    raise HTTPException(413, f"{f.filename}: exceeds the 10 MiB size limit")
                contents[f.filename or f"file-{len(contents) + 1}.csv"] = data
        finally:
            for f in files:
                await f.close()

        facts = copy.copy(state.facts)
        for name, value in (("name", business_name), ("opening_balance", opening_balance),
                            ("labor_rate", labor_rate), ("tax_reserve_rate", tax_reserve_rate)):
            if value is not None:
                setattr(facts, name, value)

        read = await asyncio.gather(*(read_file(name, data) for name, data in contents.items()))
        new = {name: records for name, (_, records, _) in zip(contents, read)}
        await categorize([t for r in new.values() for t in r.transactions])

        sources = {} if replace else dict(state.sources)
        sources.update(new)
        state.facts = facts if not dry_run else state.facts
        staged = ImportState(sources=sources, plaid_items=state.plaid_items, facts=facts)
        result = await rebuild(request, response, token, staged, sources, dry_run)
        if not dry_run:
            state.sources, state.facts = staged.sources, facts
        files_report = [{
            "name": name, "kind": plan.kind, "source": plan.source, "account": plan.account,
            "rows": rows, "transactions": len(records.transactions), "invoices": len(records.invoices),
            "jobs": len(records.jobs), "columns": {k: v for k, v in plan.columns.model_dump().items() if v},
            "notes": plan.notes} for name, (plan, records, rows) in zip(contents, read)]
        return {"files": files_report} | result

    @router.get("/import/sources")
    def import_sources(request: Request):
        _, state = session(request)
        return {"sources": [{"name": n, "transactions": len(r.transactions), "invoices": len(r.invoices),
                             "jobs": len(r.jobs)} for n, r in state.sources.items()],
                "facts": vars(state.facts), "banks_connected": len(state.plaid_items)}

    @router.post("/import/clear")
    def import_clear(request: Request, response: Response):
        """Forget every import and bank connection for this browser and go back to the sample."""
        token = request.cookies.get(cookie_name)
        imports.clear(token)
        datasets.reset(token)
        response.delete_cookie(cookie_name)
        return {"cleared": True}

    # --- Plaid ----------------------------------------------------------------------

    async def connect(request, response, token, state, client, access_token, item_id) -> dict:
        transactions, accounts, complete = await client.sync(access_token)
        records = plaid.to_records(transactions, accounts, source=f"bank:{item_id}", complete=complete)
        await categorize(records.transactions)
        state.plaid_items[item_id] = access_token
        sources = dict(state.sources) | {f"bank:{item_id}": records}
        result = await rebuild(request, response, token, state, sources)
        return result | {"bank": {"item_id": item_id, "accounts": [
            {"name": a.get("name"), "type": a.get("type"), "subtype": a.get("subtype"),
             "mask": a.get("mask"), "current_balance": (a.get("balances") or {}).get("current")}
            for a in accounts], "transactions": len(records.transactions)}}

    def plaid_client() -> plaid.PlaidClient:
        try:
            return plaid.PlaidClient()
        except plaid.PlaidError as e:
            raise HTTPException(503, str(e)) from e

    async def plaid_call(work):
        client = plaid_client()
        try:
            return await work(client)
        except plaid.PlaidError as e:
            raise HTTPException(502, str(e)) from e
        finally:
            await client.close()

    @router.get("/plaid/status")
    def plaid_status(request: Request):
        _, state = session(request)
        return {"configured": plaid.configured(), "environment": plaid.environment(),
                "banks_connected": len(state.plaid_items)}

    @router.post("/plaid/link-token")
    async def plaid_link_token(request: Request, response: Response):
        """Start Plaid Link in the browser with this token."""
        token, _ = session(request)
        set_cookie(request, response, token)
        return {"link_token": await plaid_call(lambda c: c.link_token(token[:32]))}

    @router.post("/plaid/exchange")
    async def plaid_exchange(request: Request, response: Response, body: ExchangeRequest):
        """Finish Plaid Link: trade the public token, pull transactions, rebuild the books."""
        require_ai()
        token, state = session(request)

        async def work(client):
            access_token, item_id = await client.exchange(body.public_token)
            return await connect(request, response, token, state, client, access_token, item_id)
        return await plaid_call(work)

    @router.post("/plaid/sandbox")
    async def plaid_sandbox(request: Request, response: Response, body: SandboxRequest = SandboxRequest()):
        """Sandbox only: connect a test bank without the Link UI."""
        require_ai()
        if plaid.environment() != "sandbox":
            raise HTTPException(403, "Only available with PLAID_ENV=sandbox.")
        token, state = session(request)

        async def work(client):
            public = await client.sandbox_public_token(contractor_config() if body.bank == "contractor" else None)
            access_token, item_id = await client.exchange(public)
            return await connect(request, response, token, state, client, access_token, item_id)
        return await plaid_call(work)

    @router.post("/plaid/refresh")
    async def plaid_refresh(request: Request, response: Response):
        """Pull the latest transactions from every connected bank."""
        require_ai()
        token, state = session(request)
        if not state.plaid_items:
            raise HTTPException(404, "No bank is connected.")

        async def work(client):
            result = {}
            for item_id, access_token in list(state.plaid_items.items()):
                result = await connect(request, response, token, state, client, access_token, item_id)
            return result
        return await plaid_call(work)

    return router
