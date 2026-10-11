"""Same-origin sign-in: provider credentials stay in HTTP-only cookies."""

import os

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

ACCESS_COOKIE = "toolbelt_access"
REFRESH_COOKIE = "toolbelt_refresh"


class Credentials(BaseModel):
    email: str = Field(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=128)


class Signup(Credentials):
    password: str = Field(min_length=12, max_length=128)


class Email(BaseModel):
    email: str = Field(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class Password(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class CallbackSession(BaseModel):
    access_token: str = Field(min_length=1, max_length=8192)
    refresh_token: str = Field(min_length=1, max_length=8192)


class Company(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def public_user(user):
    return {"id": user["id"], "email": user.get("email", "")}


def set_session(request, response, session):
    secure = request.url.scheme == "https" or os.getenv("COOKIE_SECURE") == "true"
    for name, value, lifetime in (
        (ACCESS_COOKIE, session["access_token"], int(session.get("expires_in", 3600))),
        (REFRESH_COOKIE, session["refresh_token"], 30 * 86400),
    ):
        response.set_cookie(name, value, max_age=lifetime, path="/api", httponly=True,
                            secure=secure, samesite="lax")


def clear_session(response):
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path="/api")


def token_from(request):
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return request.cookies.get(ACCESS_COOKIE)


def user_from(request, provider):
    token = token_from(request)
    if not token:
        raise HTTPException(401, "Sign in to access your company.")
    return token, provider.verify(token)


def build_auth_router(provider):
    router = APIRouter(prefix="/api")

    @router.get("/auth/config")
    def config():
        return {"configured": provider.configured}

    @router.post("/auth/signup")
    def signup(request: Request, response: Response, body: Signup):
        options = {}
        if site := os.getenv("PUBLIC_APP_URL"):
            options["redirect_to"] = site
        result = provider.call("POST", "/auth/v1/signup",
            params=options, body={"email": body.email.strip().lower(), "password": body.password})
        if result.get("access_token"):
            set_session(request, response, result)
            return {"signed_in": True, "user": public_user(result["user"])}
        return {"signed_in": False, "message": "Check your email to confirm your account, then sign in."}

    @router.post("/auth/login")
    def login(request: Request, response: Response, body: Credentials):
        result = provider.call("POST", "/auth/v1/token", params={"grant_type": "password"},
            body={"email": body.email.strip().lower(), "password": body.password})
        set_session(request, response, result)
        return {"user": public_user(result["user"])}

    @router.post("/auth/refresh")
    def refresh(request: Request, response: Response):
        token = request.cookies.get(REFRESH_COOKIE)
        if not token:
            raise HTTPException(401, "Please sign in again.")
        result = provider.call("POST", "/auth/v1/token", params={"grant_type": "refresh_token"},
            body={"refresh_token": token})
        set_session(request, response, result)
        return {"user": public_user(result["user"])}

    @router.post("/auth/session")
    def callback(request: Request, response: Response, body: CallbackSession):
        # Email confirmation/recovery redirects can deliver an implicit session.
        user = provider.verify(body.access_token)
        refreshed = provider.call("POST", "/auth/v1/token", params={"grant_type": "refresh_token"},
            body={"refresh_token": body.refresh_token})
        if refreshed["user"]["id"] != user["id"]:
            raise HTTPException(401, "Invalid account session.")
        set_session(request, response, refreshed)
        return {"user": public_user(user)}

    @router.post("/auth/logout")
    def logout(request: Request, response: Response):
        token = token_from(request)
        if token:
            try:
                provider.call("POST", "/auth/v1/logout", token=token, params={"scope": "local"})
            except HTTPException:
                pass  # The browser still discards credentials if the provider is unavailable.
        clear_session(response)
        return {"signed_out": True}

    @router.post("/auth/recover")
    def recover(body: Email):
        params = {"redirect_to": os.environ["PUBLIC_APP_URL"]} if os.getenv("PUBLIC_APP_URL") else {}
        provider.call("POST", "/auth/v1/recover", params=params,
            body={"email": body.email.strip().lower()})
        return {"message": "If an account exists, a password reset link has been sent."}

    @router.post("/auth/password")
    def password(request: Request, body: Password):
        token, _ = user_from(request, provider)
        provider.call("PUT", "/auth/v1/user", token=token, body={"password": body.password})
        return {"message": "Your password has been updated."}

    @router.get("/auth/me")
    def me(request: Request):
        token, user = user_from(request, provider)
        return {"user": public_user(user), "companies": provider.companies(token)}

    @router.post("/companies")
    def create_company(request: Request, body: Company):
        token, user = user_from(request, provider)
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Enter a company name.")
        rows = provider.call("POST", "/rest/v1/companies", token=token,
            body={"name": name, "owner_id": user["id"]},
            headers={"Prefer": "return=representation"}, params={"select": "id,name,created_at"})
        return {"company": rows[0]}

    return router
