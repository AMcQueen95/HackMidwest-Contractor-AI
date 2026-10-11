"""Offline provider fixture; the real account guard, routes, encryption and storage adapter run."""

import copy
import json
import os
import secrets
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient as BaseClient

from backend.app.accounts.routes import ACCESS_COOKIE
from backend.app.accounts.storage import cipher, encode_books
from backend.app.data import load_books
from backend.app.main import create_app as real_create_app


class FakeSupabase:
    configured = True

    def __init__(self):
        os.environ.setdefault("APP_DATA_KEY", Fernet.generate_key().decode())
        self.users, self.tokens, self.refreshes, self.company_rows, self.states = {}, {}, {}, {}, {}
        self.confirm_email = False
        self.calls = []

    def session(self, user):
        access, refresh = secrets.token_hex(20), secrets.token_hex(20)
        self.tokens[access], self.refreshes[refresh] = user, user
        return {"access_token": access, "refresh_token": refresh, "expires_in": 3600,
                "user": {"id": user, "email": self.users[user]["email"]}}

    def add_user(self, email=None, password="test-passphrase-123"):
        user = str(uuid4())
        self.users[user] = {"email": email or f"{user}@example.com", "password": password}
        return self.session(user)

    def verify(self, token):
        if token not in self.tokens:
            raise HTTPException(401, "Please sign in again.")
        user = self.tokens[token]
        return {"id": user, "email": self.users[user]["email"]}

    def companies(self, token):
        user = self.verify(token)["id"]
        return [{k: row[k] for k in ("id", "name", "created_at")}
                for row in self.company_rows.values() if row["owner_id"] == user]

    def company(self, user, name="Test company", seed=False):
        company = str(uuid4())
        row = {"id": company, "name": name, "owner_id": user, "created_at": "2026-10-11T00:00:00Z"}
        self.company_rows[company] = row
        if seed:
            data = {"books": encode_books(load_books()), "revision": "sample"}
            self.states[company] = {"revision": secrets.token_hex(16),
                "payload": cipher().encrypt(json.dumps(data).encode()).decode()}
        return {k: row[k] for k in ("id", "name", "created_at")}

    def load(self, token, company):
        self.verify(token)
        return copy.deepcopy(self.states.get(company))

    def save(self, token, company, previous, revision, payload):
        user = self.verify(token)["id"]
        assert self.company_rows[company]["owner_id"] == user
        if self.states.get(company, {}).get("revision") != previous:
            raise HTTPException(409, "Records changed in another request. Refresh and try again.")
        self.states[company] = {"revision": revision, "payload": payload}

    def call(self, method, path, *, token=None, body=None, params=None, headers=None):
        self.calls.append((method, path))
        if path == "/auth/v1/signup":
            session = self.add_user(body["email"], body["password"])
            return {"user": session["user"]} if self.confirm_email else session
        if path == "/auth/v1/token":
            if params["grant_type"] == "refresh_token":
                user = self.refreshes.get(body["refresh_token"])
            else:
                user = next((id for id, row in self.users.items()
                    if row["email"] == body["email"] and row["password"] == body["password"]), None)
            if not user:
                raise HTTPException(401, "Email or password is incorrect, or email is not confirmed.")
            return self.session(user)
        if path == "/auth/v1/recover":
            return {}
        if path == "/auth/v1/logout":
            user = self.verify(token)["id"]
            self.tokens.pop(token, None)
            self.refreshes = {k: v for k, v in self.refreshes.items() if v != user}
            return {}
        if path == "/auth/v1/user" and method == "PUT":
            user = self.verify(token)
            self.users[user["id"]]["password"] = body["password"]
            return user
        if path == "/rest/v1/companies" and method == "POST":
            user = self.verify(token)["id"]
            assert body["owner_id"] == user
            return [self.company(user, body["name"])]
        raise AssertionError(f"Unexpected provider call: {method} {path}")


def create_app(*args, **kwargs):
    kwargs.setdefault("auth_backend", FakeSupabase())
    return real_create_app(*args, **kwargs)


class AuthTestClient(BaseClient):
    def __init__(self, app, **kwargs):
        provider = app.state.accounts
        session = provider.add_user()
        company = provider.company(session["user"]["id"], seed=True)
        kwargs["headers"] = {"Authorization": f"Bearer {session['access_token']}",
                             "X-Company-ID": company["id"], **kwargs.get("headers", {})}
        super().__init__(app, **kwargs)
