"""Encrypted company snapshots with optimistic database writes and bounded AI caches."""

import json
import os
import secrets
from collections import OrderedDict
from dataclasses import asdict
from datetime import date
from threading import Lock

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from backend.app.agent_context import AgentState
from backend.app.data import load_books_from_uploads
from backend.app.data.loader import COLUMNS
from backend.app.datasets import Dataset, DatasetStore
from backend.app.integrations.records import BusinessFacts, Invoice, Job, Records, Transaction
from backend.app.integrations.sessions import ImportState
from .context import Workspace, active_workspace


def cipher():
    try:
        return Fernet(os.environ["APP_DATA_KEY"].encode())
    except (KeyError, ValueError):
        raise HTTPException(503, "Financial storage encryption is not configured.") from None


def encode_books(books):
    files = {"business.json": json.dumps(books.business)}
    for name, columns in COLUMNS.items():
        frame = getattr(books, name[:-4]).loc[:, list(columns)].copy()
        for column in frame:
            if column in {"date", "start_date", "end_date", "issued", "due", "paid_date"}:
                frame[column] = frame[column].dt.strftime("%Y-%m-%d").fillna("")
        files[name] = frame.to_csv(index=False)
    return files


def encode_imports(state):
    return json.loads(json.dumps(asdict(state), default=lambda value: value.isoformat()))


def decode_imports(payload):
    sources = {}
    for name, data in payload.get("sources", {}).items():
        data = dict(data)
        for key, cls, dates in [
            ("transactions", Transaction, ["date"]),
            ("invoices", Invoice, ["issued", "due", "paid_date"]),
            ("jobs", Job, ["start_date", "end_date"]),
        ]:
            records = []
            for original in data.get(key, []):
                row = dict(original)
                for column in dates:
                    if row.get(column):
                        row[column] = date.fromisoformat(row[column])
                records.append(cls(**row))
            data[key] = records
        sources[name] = Records(**data)
    return ImportState(sources=sources, plaid_items=payload.get("plaid_items", {}),
                       facts=BusinessFacts(**payload.get("facts", {})))


class AccountDatasetStore(DatasetStore):
    def __init__(self, sample):
        super().__init__(sample)
        self._ai = OrderedDict()
        self._ai_lock = Lock()

    def ai_state(self, company_id, revision):
        key = (company_id, revision)
        with self._ai_lock:
            state = self._ai.setdefault(key, AgentState())
            self._ai.move_to_end(key)
            while len(self._ai) > 32:
                self._ai.popitem(last=False)
            return state

    def get(self, token):
        if workspace := active_workspace.get():
            if workspace.dataset is None:
                raise HTTPException(409, "Upload financial records for this company first.")
            return workspace.dataset
        # Internal inspection only; no private API runs without an authorized workspace.
        return super().get(token)

    def ensure(self, token):
        if workspace := active_workspace.get():
            return workspace.company["id"], workspace.dataset or self.sample
        return super().ensure(token)

    def replace(self, books, token, *, is_sample=False):
        if workspace := active_workspace.get():
            revision = secrets.token_hex(12)
            workspace.data["books"] = encode_books(books)
            workspace.data["revision"] = revision
            if is_sample:  # a trade's sample business, loaded during onboarding
                workspace.data["is_sample"] = True
            else:
                workspace.data.pop("is_sample", None)
            workspace.dataset = Dataset(books, is_sample, revision,
                self.ai_state(workspace.company["id"], revision))
            return workspace.company["id"], workspace.dataset
        return super().replace(books, token, is_sample=is_sample)

    def reset(self, token):
        if workspace := active_workspace.get():
            kept = {k: workspace.data[k] for k in ("trades", "trade_other", "trade_done") if k in workspace.data}
            workspace.data.clear()
            workspace.data.update(kept)  # clearing books keeps the company's kinds of work
            workspace.dataset = None
            workspace.imports = ImportState()
        else:
            super().reset(token)


def load_workspace(provider, store, token, user, company_id):
    companies = provider.companies(token)
    company = next((c for c in companies if c["id"] == company_id), None)
    if company is None:
        raise HTTPException(404, "Company not found or you do not have access.")
    row = provider.load(token, company_id)
    data = {}
    if row:
        try:
            data = json.loads(cipher().decrypt(row["payload"].encode()))
        except (InvalidToken, ValueError, KeyError):
            raise HTTPException(503, "Saved financial records could not be read. Check server storage configuration.") from None
    dataset = None
    if files := data.get("books"):
        books = load_books_from_uploads(files)
        revision = data["revision"]
        dataset = Dataset(books, bool(data.get("is_sample")), revision, store.ai_state(company_id, revision))
    return Workspace(user["id"], company, token, data,
        row["revision"] if row else None, dataset, decode_imports(data.get("imports", {})))


def snapshot(workspace):
    data = dict(workspace.data)
    imports = encode_imports(workspace.imports)
    if imports["sources"] or imports["plaid_items"]:
        data["imports"] = imports
    else:
        data.pop("imports", None)
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def save_workspace(provider, workspace, original):
    current = snapshot(workspace)
    if current == original:
        return
    encrypted = cipher().encrypt(current.encode()).decode()
    provider.save(workspace.token, workspace.company["id"], workspace.database_revision,
                  secrets.token_hex(16), encrypted)
