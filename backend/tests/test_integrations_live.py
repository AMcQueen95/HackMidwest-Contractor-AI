"""Live import checks: real agents read the messy sample exports in test-data/imports.

Skipped by default. Run with:
    RUN_LIVE_TESTS=1 python -m pytest backend/tests/test_integrations_live.py -v
The Plaid test also needs Plaid sandbox keys and a saved test account in backend/.env
(python scripts/create_plaid_sandbox_bank.py).
"""

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from backend.app.main import create_app

ENV = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
SAMPLES = Path(__file__).resolve().parents[2] / "test-data" / "imports"
pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1")


@pytest.fixture
def client(monkeypatch):
    if not ENV.get("ANTHROPIC_API_KEY"):
        pytest.skip("no ANTHROPIC_API_KEY in backend/.env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", ENV["ANTHROPIC_API_KEY"])
    return TestClient(create_app())


def test_messy_exports_are_identified_and_combined(client):
    files = [("files", (p.name, p.read_bytes(), "text/csv")) for p in sorted(SAMPLES.iterdir())
             if p.suffix.lower() == ".csv"]
    result = client.post("/api/import", files=files, data={"labor_rate": "50"}).json()
    kinds = {f["name"]: f["kind"] for f in result["files"]}

    assert kinds["Chase4421_Activity_20261001.CSV"] == "transactions"
    assert kinds["amex_activity.csv"] == "transactions"
    assert kinds["FirstCU_savings.csv"] == "transactions"
    assert kinds["Ridgeline Heating & Air_Invoice List.csv"] == "invoices"
    assert kinds["jobs_export_2026-10-01.csv"] == "jobs"
    assert kinds["crew_contacts.csv"] == "unknown"

    summary, report = result["summary"], result["report"]
    assert summary["excluded_transactions"] == 8  # 4 card payments, 2 savings transfers each way
    assert summary["payment_dates_matched"] == 8
    assert report["receivables"]["total_outstanding"] == 21000
    assert report["cash_balance"]["balance"] == pytest.approx(20433.31 + 18213.40)  # checking + savings, latest balances
    linked = {i["customer"] for i in report["receivables"]["invoices"]}
    assert linked == {"Westport Dental Group", "Brookside Property Mgmt"}


def test_plaid_sandbox_contractor_bank(client, monkeypatch):
    needed = ("PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_SANDBOX_ACCESS_TOKEN")
    if not all(ENV.get(k) for k in needed):
        pytest.skip("needs Plaid keys and a saved test account (scripts/create_plaid_sandbox_bank.py)")
    for key in needed + ("PLAID_SANDBOX_ITEM_ID",):
        monkeypatch.setenv(key, ENV.get(key) or "")
    result = client.post("/api/plaid/sandbox").json()
    assert result.get("applied"), result
    assert result["bank"]["transactions"] > 100
    totals = result["summary"]["totals_by_category"]
    assert totals["income"] > 0 and totals["payroll"] < 0 and totals["materials"] < 0
    assert result["summary"]["excluded_transactions"] > 0  # card payments and owner draws
    bank_now = sum(a["current_balance"] for a in result["bank"]["accounts"] if a["type"] == "depository")
    assert result["report"]["cash_balance"]["balance"] == bank_now  # cash matches the bank today
