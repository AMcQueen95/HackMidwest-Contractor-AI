"""Create the HVAC shop's test bank account in your Plaid sandbox, once.

Plaid keeps the account; this saves its access token to backend/.env as
PLAID_SANDBOX_ACCESS_TOKEN, and the app connects to that same account from then
on. Run again only to replace it (for example, to refresh the dates).

    python scripts/create_plaid_sandbox_bank.py
    python scripts/create_plaid_sandbox_bank.py --plaid-default   # Plaid's generic test user instead
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"
load_dotenv(ENV)

from backend.app.integrations.plaid import PlaidClient, environment  # noqa: E402
from plaid_sandbox_data import contractor_config  # noqa: E402


def save(values: dict[str, str]) -> None:
    lines = [line for line in ENV.read_text().splitlines() if line.split("=", 1)[0] not in values]
    lines += [f"{key}={value}" for key, value in values.items()]
    ENV.write_text("\n".join(lines) + "\n")


async def main(plaid_default: bool) -> None:
    if environment() != "sandbox":
        raise SystemExit("PLAID_ENV must be sandbox.")
    client = PlaidClient()
    try:
        public = await client.sandbox_public_token(None if plaid_default else contractor_config())
        access_token, item_id = await client.exchange(public)
    finally:
        await client.close()
    save({"PLAID_SANDBOX_ACCESS_TOKEN": access_token, "PLAID_SANDBOX_ITEM_ID": item_id})
    print(f"Created test bank account {item_id} in Plaid's sandbox and saved its token to backend/.env.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plaid-default", action="store_true", help="use Plaid's generic test user")
    asyncio.run(main(parser.parse_args().plaid_default))
