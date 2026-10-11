"""Any-CSV import and Plaid, with fake agents and a fake Plaid server: no network."""

import json
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.integrations import csv_import, plaid, routes
from backend.app.integrations.ai import Columns, FileInterpretation
from backend.app.integrations.records import BusinessFacts, Invoice, Job, Records, Transaction, assemble
from backend.app.main import create_app


# --- Reading values ------------------------------------------------------------------

@pytest.mark.parametrize("raw,value", [
    ("$1,234.56", 1234.56), ("(1,234.56)", -1234.56), ("1234.56-", -1234.56), ("-$12", -12.0),
    ("12.00 CR", 12.0), ("40.00 DR", -40.0), ("", None), ("n/a", None)])
def test_parse_amount_handles_export_formats(raw, value):
    assert csv_import.parse_amount(raw) == value


def plan(kind="transactions", sign="inflow_positive", account="bank", header_row=0, **columns):
    return FileInterpretation(kind=kind, source="test", account=account, header_row=header_row,
                              columns=Columns(**columns), amount_sign=sign,
                              outflow_values=["DEBIT"] if sign == "direction_column" else [])


def test_bank_export_newest_first_gives_opening_balance():
    rows = csv_import._rows("Date,Desc,Amount,Balance\n09/02/2026,Fuel,-50,950\n09/01/2026,Deposit,500,1000\n", 0)
    out = csv_import.convert(rows, plan(date="Date", description="Desc", amount="Amount", balance="Balance"), "bank.csv")
    assert [t.amount for t in out.transactions] == [-50, 500]
    assert out.opening_balance == 500  # 1000 after the first deposit of 500
    assert out.closing_balance == 950  # newest row's balance


@pytest.mark.parametrize("sign,row,expected", [
    ("outflow_positive", {"D": "2026-09-01", "X": "Fuel", "A": "40"}, -40),
    ("split_columns", {"D": "2026-09-01", "X": "Pay", "Out": "", "In": "300"}, 300),
    ("direction_column", {"D": "2026-09-01", "X": "Fuel", "A": "40", "T": "DEBIT"}, -40),
])
def test_money_direction_conventions(sign, row, expected):
    p = plan(sign=sign, date="D", description="X", amount=None if sign == "split_columns" else "A",
             debit="Out" if sign == "split_columns" else None, credit="In" if sign == "split_columns" else None,
             direction="T" if sign == "direction_column" else None)
    assert csv_import.convert([row], p, "f.csv").transactions[0].amount == expected


def test_columns_the_file_does_not_have_are_ignored_with_a_warning():
    out = csv_import.convert([{"Date": "2026-09-01", "Amount": "5"}],
                             plan(date="Date", amount="Amount", description="Memo"), "f.csv")
    assert out.transactions[0].description == "Transaction"
    assert any("'Memo'" in w for w in out.warnings)


def test_preamble_lines_and_totals_row_are_skipped():
    text = "My Shop\nInvoice List\n\nDate,Num,Customer,Amount,Open balance\n09/01/2026,7,Ann,100.00,0.00\nTOTAL,,,100.00,0.00\n"
    out = csv_import.convert(csv_import._rows(text, 3), plan(
        kind="invoices", header_row=3, issued="Date", invoice_id="Num", customer="Ann" and "Customer",
        invoice_total="Amount", open_balance="Open balance"), "qb.csv")
    assert [(i.invoice_id, i.paid_amount) for i in out.invoices] == [("7", 100.0)]
    assert any("skipped 1" in w for w in out.warnings)


# --- Assembling books -----------------------------------------------------------------

def tx(day, amount, desc, category, source="bank.csv"):
    return Transaction(date=date(2026, 9, day), amount=amount, description=desc, category=category,
                       vendor=desc, source=source)


def test_assembly_dedupes_excludes_links_and_matches_payments():
    records = Records(
        transactions=[tx(2, 900, "Payment Ann", "income"), tx(3, -200, "Supply house", "materials"),
                      tx(3, -200, "Supply house", "materials", source="ledger.csv"),  # same payment twice
                      tx(20, -1500, "Card payment", "transfer"), tx(28, -3000, "Owner draw", "owner")],
        invoices=[Invoice("7", "Ann", date(2026, 9, 1), date(2026, 9, 15), 900, paid_amount=900),
                  Invoice("8", "Bo", date(2026, 9, 5), date(2026, 9, 20), 400)],
        jobs=[Job("J1", "ann", "AC repair", date(2026, 8, 30), date(2026, 9, 1), 900, labor_hours=3)],
        opening_balance=5000)
    books, warnings, summary = assemble(records, BusinessFacts(name="Shop", labor_rate=50))

    assert summary["transactions"] == 2 and summary["excluded_transactions"] == 2
    assert any("more than one file" in w for w in warnings)
    assert any("transfer" in w for w in warnings) and any("owner" in w for w in warnings)
    linked = dict(zip(books.invoices["invoice_id"], books.invoices["job_id"]))
    assert linked["7"] == "J1"  # matched to the jobs export by customer and price
    assert linked["8"] == "JOB-8"  # no job: one made from the invoice
    assert str(books.invoices.set_index("invoice_id").loc["7", "paid_date"].date()) == "2026-09-02"
    assert books.business["opening_balance"] == 5000


def test_assembly_needs_transactions():
    with pytest.raises(ValueError, match="No business transactions"):
        assemble(Records(), BusinessFacts())


# --- The import endpoint -----------------------------------------------------------------

BANK = "Date,Description,Amount,Balance\n2026-09-02,STRIPE PAYOUT,800.00,1800.00\n2026-09-01,HVAC SUPPLY,-200.00,1000.00\n"
INVOICES = "Num,Customer,Date,Total,Balance due\n55,Ann,2026-09-01,800.00,0\n56,Bo,2026-09-03,400.00,400.00\n"
PLANS = {
    "bank.csv": plan(date="Date", description="Description", amount="Amount", balance="Balance"),
    "inv.csv": plan(kind="invoices", invoice_id="Num", customer="Customer", issued="Date",
                    invoice_total="Total", open_balance="Balance due"),
}


@pytest.fixture
def client(monkeypatch):
    async def fake_identify(filename, lines):
        return PLANS[filename]

    async def fake_categorize(transactions, **kwargs):
        for t in transactions:
            t.category, t.vendor = ("income" if t.amount > 0 else "materials"), t.description.title()

    monkeypatch.setattr(csv_import, "identify", fake_identify)
    monkeypatch.setattr(routes, "categorize", fake_categorize)
    return TestClient(create_app())


def upload(client, *names, **data):
    content = {"bank.csv": BANK, "inv.csv": INVOICES}
    return client.post("/api/import", files=[("files", (n, content[n], "text/csv")) for n in names], data=data)


def test_import_builds_books_and_later_imports_add_up(client):
    first = upload(client, "bank.csv", business_name="Ann's HVAC").json()
    assert first["applied"] and first["files"][0]["kind"] == "transactions"
    assert first["report"]["business"]["name"] == "Ann's HVAC"
    assert first["report"]["cash_balance"]["balance"] == 1800  # matches the bank's latest balance

    second = upload(client, "inv.csv").json()
    assert {s["name"] for s in second["sources"]} == {"bank.csv", "inv.csv"}
    assert second["report"]["receivables"]["total_outstanding"] == 400
    assert client.get("/api/report").json()["business"]["name"] == "Ann's HVAC"


def test_dry_run_and_replace_and_clear(client):
    upload(client, "bank.csv")
    dry = upload(client, "inv.csv", dry_run="true").json()
    assert dry["applied"] is False and "report" not in dry
    assert [s["name"] for s in client.get("/api/import/sources").json()["sources"]] == ["bank.csv"]

    replaced = upload(client, "bank.csv", replace="true").json()
    assert [s["name"] for s in replaced["sources"]] == ["bank.csv"]

    client.post("/api/import/clear")
    assert client.get("/api/report").json()["business"]["name"] == "Ridgeline Heating & Air"


# --- Plaid ------------------------------------------------------------------------------

PLAID_TX = [
    {"transaction_id": "t1", "account_id": "chk", "amount": -1200.0, "date": "2026-09-02", "name": "ACH DEPOSIT MILLER",
     "merchant_name": None, "pending": False, "personal_finance_category": {"primary": "INCOME"}},
    {"transaction_id": "t2", "account_id": "chk", "amount": 300.0, "date": "2026-09-03", "name": "JOHNSTONE SUPPLY",
     "merchant_name": "Johnstone Supply", "pending": False, "personal_finance_category": {"primary": "GENERAL_MERCHANDISE"}},
    {"transaction_id": "t3", "account_id": "card", "amount": 80.0, "date": "2026-09-04", "name": "QT 0145",
     "merchant_name": "QuikTrip", "pending": False, "personal_finance_category": {"primary": "TRANSPORTATION"}},
    {"transaction_id": "t4", "account_id": "chk", "amount": 50.0, "date": "2026-09-05", "name": "PENDING THING",
     "merchant_name": None, "pending": True},
]
ACCOUNTS = [{"account_id": "chk", "type": "depository", "subtype": "checking", "name": "Checking", "mask": "4421",
             "balances": {"current": 5900.0}},
            {"account_id": "card", "type": "credit", "subtype": "credit card", "name": "Card", "mask": "9001",
             "balances": {"current": 80.0}}]


def fake_plaid(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["client_id"] == "cid" and body["secret"] == "sec"
    path = request.url.path
    if path in ("/sandbox/public_token/create", "/item/public_token/exchange"):
        raise AssertionError("the saved test account should be reused, not created")
    if "access_token" in body:
        assert body["access_token"] == "access-saved"
    if path == "/accounts/get":
        return httpx.Response(200, json={"accounts": ACCOUNTS})
    if path == "/transactions/sync":
        # Page 1 (has_more), then the rest, then nothing new: like Plaid finishing its history.
        pages = {"": (PLAID_TX[:2], "c1", True), "c1": (PLAID_TX[2:], "c2", False), "c2": ([], "c2", False)}
        added, cursor, more = pages[body["cursor"]]
        return httpx.Response(200, json={
            "added": added, "modified": [], "removed": [], "accounts": ACCOUNTS, "next_cursor": cursor,
            "has_more": more, "transactions_update_status": "HISTORICAL_UPDATE_COMPLETE"})
    return httpx.Response(400, json={"error_code": "UNEXPECTED", "error_message": path})


def test_plaid_records_flip_signs_skip_pending_and_find_starting_cash():
    records = plaid.to_records(PLAID_TX, ACCOUNTS, "bank:item")
    assert [(t.amount, t.account) for t in records.transactions] == [
        (1200.0, "bank"), (-300.0, "bank"), (-80.0, "credit_card")]
    assert records.closing_balance == 5900.0  # checking only; the card balance is money owed


def test_plaid_sandbox_reuses_the_saved_test_account(client, monkeypatch):
    monkeypatch.setenv("PLAID_CLIENT_ID", "cid")
    monkeypatch.setenv("PLAID_SECRET", "sec")
    monkeypatch.setenv("PLAID_SANDBOX_ACCESS_TOKEN", "access-saved")
    monkeypatch.setenv("PLAID_SANDBOX_ITEM_ID", "item-1")
    real_client, real_sync = plaid.PlaidClient, plaid.PlaidClient.sync
    monkeypatch.setattr(plaid.PlaidClient, "sync", lambda self, token: real_sync(self, token, quiet_seconds=0))
    monkeypatch.setattr(plaid, "PlaidClient", lambda: real_client(httpx.MockTransport(fake_plaid)))
    result = client.post("/api/plaid/sandbox").json()

    assert result["applied"] and result["bank"]["transactions"] == 3
    assert {a["mask"] for a in result["bank"]["accounts"]} == {"4421", "9001"}
    assert result["report"]["cash_balance"]["balance"] == 5900.0  # cash matches the bank today
    assert client.get("/api/plaid/status").json()["banks_connected"] == 1


def test_plaid_without_keys_says_how_to_set_it_up(client, monkeypatch):
    monkeypatch.delenv("PLAID_CLIENT_ID", raising=False)
    response = client.post("/api/plaid/sandbox")
    assert response.status_code == 503 and "PLAID_CLIENT_ID" in response.json()["detail"]


def test_plaid_sandbox_without_a_saved_account_says_how_to_create_one(client, monkeypatch):
    monkeypatch.setenv("PLAID_CLIENT_ID", "cid")
    monkeypatch.setenv("PLAID_SECRET", "sec")
    monkeypatch.delenv("PLAID_SANDBOX_ACCESS_TOKEN", raising=False)
    response = client.post("/api/plaid/sandbox")
    assert response.status_code == 503 and "create_plaid_sandbox_bank.py" in response.json()["detail"]
