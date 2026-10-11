"""Supabase Auth/PostgREST client. Uses the public key and the user's JWT, never service-role access."""

import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException


class SupabaseBackend:
    def __init__(self, *, transport=None):
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
        self.transport = transport

    @property
    def configured(self):
        return bool(self.url and self.key)

    def call(self, method, path, *, token=None, body=None, params=None, headers=None):
        if not self.configured:
            raise HTTPException(503, "Account services are not configured yet.")
        if urlsplit(self.url).scheme != "https":
            raise HTTPException(503, "SUPABASE_URL must use HTTPS.")
        request_headers = {"apikey": self.key, **(headers or {})}
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        try:
            with httpx.Client(timeout=15, transport=self.transport) as client:
                result = client.request(method, self.url + path, json=body,
                    params=params, headers=request_headers)
        except httpx.HTTPError:
            raise HTTPException(503, "Account services could not be reached. Please try again.") from None
        if result.status_code >= 400:
            if result.status_code == 429:
                raise HTTPException(429, "Too many attempts. Please wait before trying again.")
            if result.status_code in (401, 403):
                raise HTTPException(401, "Please sign in again.")
            if path == "/auth/v1/token":
                raise HTTPException(401, "Email or password is incorrect, or email is not confirmed.")
            if path.startswith("/rest/"):
                if result.status_code == 409:
                    raise HTTPException(409, "Records changed in another request. Refresh and try again.")
                raise HTTPException(503, "Company storage is unavailable. Check the database migration.")
            raise HTTPException(400, "The account request could not be completed. Check your details and try again.")
        return result.json() if result.content else {}

    def verify(self, token):
        user = self.call("GET", "/auth/v1/user", token=token)
        if not user.get("id"):
            raise HTTPException(401, "Please sign in again.")
        return user

    def companies(self, token):
        return self.call("GET", "/rest/v1/companies", token=token,
            params={"select": "id,name,created_at", "order": "created_at.asc"})

    def load(self, token, company_id):
        rows = self.call("GET", "/rest/v1/company_state", token=token,
            params={"company_id": f"eq.{company_id}", "select": "revision,payload"})
        return rows[0] if rows else None

    def save(self, token, company_id, previous_revision, revision, payload):
        body = {"company_id": company_id, "revision": revision, "payload": payload}
        if previous_revision is None:
            self.call("POST", "/rest/v1/company_state", token=token, body=body)
        else:
            rows = self.call("PATCH", "/rest/v1/company_state", token=token, body=body,
                params={"company_id": f"eq.{company_id}", "revision": f"eq.{previous_revision}"},
                headers={"Prefer": "return=representation"})
            if not rows:
                raise HTTPException(409, "Records changed in another request. Refresh and try again.")
