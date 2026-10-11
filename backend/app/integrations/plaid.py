"""Bank connections through Plaid: link, exchange, and sync transactions and balances.

Uses Plaid's REST API directly. Configure PLAID_CLIENT_ID, PLAID_SECRET and
PLAID_ENV (sandbox by default) in backend/.env.
"""

import asyncio
import json
import os
from datetime import date, timedelta

import httpx

from backend.app.integrations.records import Records, Transaction

HOSTS = {"sandbox": "https://sandbox.plaid.com", "production": "https://production.plaid.com"}
SANDBOX_INSTITUTION = "ins_109508"  # First Platypus Bank: non-OAuth, works with custom users


class PlaidError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.getenv("PLAID_CLIENT_ID") and os.getenv("PLAID_SECRET"))


def environment() -> str:
    return os.getenv("PLAID_ENV", "sandbox")


SETUP_MESSAGE = ("Plaid isn't set up. Add PLAID_CLIENT_ID and PLAID_SECRET to backend/.env "
                 "(free sandbox keys at dashboard.plaid.com).")


class PlaidClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        if not configured():
            raise PlaidError(SETUP_MESSAGE)
        if environment() not in HOSTS:
            raise PlaidError("PLAID_ENV must be sandbox or production.")
        self._http = httpx.AsyncClient(base_url=HOSTS[environment()], timeout=30, transport=transport)
        self._auth = {"client_id": os.environ["PLAID_CLIENT_ID"], "secret": os.environ["PLAID_SECRET"]}

    async def close(self):
        await self._http.aclose()

    async def _post(self, path: str, body: dict) -> dict:
        response = await self._http.post(path, json={**self._auth, **body})
        data = response.json()
        if response.status_code != 200:
            raise PlaidError(f"Plaid {path}: {data.get('error_code')}: {data.get('error_message')}")
        return data

    async def link_token(self, user_id: str) -> str:
        """For the frontend's Plaid Link button."""
        data = await self._post("/link/token/create", {
            "user": {"client_user_id": user_id}, "client_name": "Toolbelt CFO",
            "products": ["transactions"], "country_codes": ["US"], "language": "en",
            "transactions": {"days_requested": 730}})
        return data["link_token"]

    async def exchange(self, public_token: str) -> tuple[str, str]:
        data = await self._post("/item/public_token/exchange", {"public_token": public_token})
        return data["access_token"], data["item_id"]

    async def sandbox_public_token(self, config: dict | None = None) -> str:
        """Sandbox only: skip Link. With a config, the bank holds exactly those transactions."""
        options = {"override_username": "user_custom", "override_password": json.dumps(config)} if config else {}
        data = await self._post("/sandbox/public_token/create", {
            "institution_id": SANDBOX_INSTITUTION, "initial_products": ["transactions"],
            "options": {**options, "transactions": {"days_requested": 730}}})
        return data["public_token"]

    async def sync(self, access_token: str, wait_seconds: float = 60,
                   quiet_seconds: float = 5) -> tuple[list[dict], list[dict], bool]:
        """All transactions on the item, its accounts, and whether the full history arrived.
        Plaid sends the last 30 days first and older history shortly after."""
        added, accounts, cursor, complete = {}, {}, "", False
        clock = asyncio.get_running_loop().time
        deadline, last_change = clock() + wait_seconds, clock()
        while True:
            data = await self._post("/transactions/sync", {"access_token": access_token, "cursor": cursor,
                                                           "count": 500})
            changes = data["added"] + data["modified"]
            for t in changes:
                added[t["transaction_id"]] = t
            if changes or data["removed"]:
                last_change = clock()
            for t in data["removed"]:
                added.pop(t["transaction_id"], None)
            for a in data.get("accounts", []):
                accounts[a["account_id"]] = a
            cursor = data["next_cursor"]
            if data["has_more"]:
                continue
            # Plaid can label the first 30 days "history complete" and deliver the older history
            # a few seconds later, so stop only once it has been complete and quiet for a while.
            complete = data.get("transactions_update_status") == "HISTORICAL_UPDATE_COMPLETE"
            if (complete and clock() - last_change >= quiet_seconds) or clock() > deadline:
                break
            await asyncio.sleep(1 if complete else 2)
        # Balances as of now (sync's account list only covers accounts with changes).
        accounts = {a["account_id"]: a for a in (await self._post(
            "/accounts/get", {"access_token": access_token}))["accounts"]} or accounts
        return list(added.values()), list(accounts.values()), complete


def to_records(transactions: list[dict], accounts: list[dict], source: str, complete: bool = True) -> Records:
    """Plaid transactions and balances as normalized records (money in positive)."""
    kinds = {a["account_id"]: a for a in accounts}
    out = Records()
    for t in transactions:
        if t.get("pending"):
            continue
        account = kinds.get(t["account_id"], {})
        category = (t.get("personal_finance_category") or {})
        out.transactions.append(Transaction(
            date=date.fromisoformat(t["date"]), amount=round(-float(t["amount"]), 2),
            description=t.get("original_description") or t.get("name") or t.get("merchant_name") or "Transaction",
            vendor=t.get("merchant_name") or "",
            hint=" / ".join(filter(None, [category.get("primary"), category.get("detailed")])),
            source=source, account="credit_card" if account.get("type") == "credit" else "bank"))

    # Cash in the bank today: checking and savings balances (cards are money owed, not cash).
    balances = [float(a["balances"]["current"]) for a in accounts
                if a.get("type") == "depository" and (a.get("balances") or {}).get("current") is not None]
    out.closing_balance = round(sum(balances), 2) if balances else None
    if not complete:
        out.warnings.append(f"{source}: the bank is still sending older history. Refresh in a minute "
                            f"to pull the rest.")
    if not out.transactions:
        out.warnings.append(f"{source}: the bank returned no posted transactions yet.")
    return out
