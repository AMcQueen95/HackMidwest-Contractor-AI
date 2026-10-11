"""Explicit offline browser-test entry point. Never used by production startup."""

from backend.tests.account_helpers import FakeSupabase
from backend.app.main import create_app

provider = FakeSupabase()
app = create_app(auth_backend=provider)
