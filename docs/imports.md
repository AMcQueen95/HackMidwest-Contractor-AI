# Getting a business's records in

Owners shouldn't have to reformat anything. Two ways in, both backend only for now:

- **Any CSV exports.** Bank and card statements, QuickBooks reports, field-service app exports (Jobber, Housecall Pro, ServiceTitan) or anything else, as many files as they have.
- **A bank connection through Plaid.** Checking, savings and card accounts, pulled directly.

Both add up per browser: upload a bank export, then an invoice export, then connect a card account, and each step rebuilds one set of books from everything so far.

## How CSV import works

1. **Identify** (`integrations/ai.py`, Claude Haiku 5.5): an agent reads the file name and first 25 lines and says what the file is (transactions, invoices, jobs or unknown), which line is the header, which column holds which field, and how money direction is shown (signed, charges-positive, split debit/credit, or a debit/credit column). It never sees or produces values that go into the books.
2. **Convert** (`integrations/csv_import.py`): code reads every row using that description. It handles `$1,234.56`, `(1,234.56)`, `12.00 CR`, title lines above the header, totals rows, and newest-first files. A column the agent names but the file lacks is ignored with a warning.
3. **Categorize** (`integrations/ai.py`, Claude Haiku 5.5): an agent gives each distinct description a clean vendor name and one category: income, materials, payroll, subcontractors, fuel, vehicle, equipment, insurance, rent, utilities, software, marketing, permits, bank_fees, taxes or overhead. Transfers between the business's own accounts (including credit card payments), owner draws and loans are excluded from profit and listed in the warnings.
4. **Assemble** (`integrations/records.py`): duplicates across files are dropped. Invoices are linked to jobs by ID, or by customer and price when the apps don't share IDs; invoices with no job get one. Missing payment dates come from matching customer deposits. Cash is anchored to what the bank holds today (the latest balance in a bank export, or Plaid's current balance), so it stays right even though transfers and owner draws are left out of profit. The result is the usual four books files, validated by `data/loader.py` before anything is replaced.

## Endpoints

| Endpoint | Does |
| --- | --- |
| `POST /api/import` | Multipart `files` (1–20 CSVs, 10 MiB each). Optional form fields: `business_name`, `opening_balance`, `labor_rate`, `tax_reserve_rate`, `replace` (start over), `dry_run` (show the interpretation without applying). Returns each file's interpretation, warnings, a summary and the new report. |
| `GET /api/import/sources` | What this browser has imported so far |
| `POST /api/import/clear` | Forget all imports and bank connections; back to the sample |
| `GET /api/plaid/status` | Whether Plaid keys are set and how many banks are connected |
| `POST /api/plaid/link-token` | A token for Plaid Link in the browser |
| `POST /api/plaid/exchange` | `{"public_token": ...}` from Plaid Link: connects the bank, pulls transactions and balances, rebuilds the books |
| `POST /api/plaid/sandbox` | Sandbox only, no UI needed. `{"bank": "contractor"}` (default) loads a realistic HVAC shop checking account and card; `{"bank": "plaid"}` uses Plaid's generic test data |
| `POST /api/plaid/refresh` | Pull the latest from every connected bank |

Access tokens stay on the server, in memory, per browser.

## Plaid setup

1. Sign up at [dashboard.plaid.com](https://dashboard.plaid.com) (free) and copy the sandbox **client ID** and **secret** from Developers → Keys.
2. Add them to `backend/.env` as `PLAID_CLIENT_ID` and `PLAID_SECRET`, with `PLAID_ENV=sandbox`.
3. Try it: `curl -X POST localhost:8000/api/plaid/sandbox -H 'Content-Type: application/json' -d '{}'`

## Testing

- `python scripts/generate_import_samples.py` regenerates the messy sample exports in `test-data/imports/`: a newest-first Chase checking export with balances, an Amex card export, a QuickBooks Invoice List with title lines and a totals row, a Jobber jobs export, a credit union file with split debit/credit columns, and a crew contact list that should be rejected.
- `python -m pytest backend/tests/test_integrations.py` runs offline with fake agents and a fake Plaid server.
- `RUN_LIVE_TESTS=1 python -m pytest backend/tests/test_integrations_live.py -v` runs the real agents on the sample exports, and Plaid sandbox if keys are set.

## Known limits

- Bank transactions aren't linked to jobs, so job profit from imports counts labor but not materials. Linking purchases to jobs is a next step.
- Cash is unknown (set to $0 with a warning) unless a bank export has a balance column, Plaid is connected, or the owner enters a starting balance.
- Plaid's sandbox can deliver older history a few seconds after the first 30 days, so a connection waits until Plaid has been complete and quiet for 5 seconds. In production, the `SYNC_UPDATES_AVAILABLE` webhook plus `/api/plaid/refresh` is the better trigger.
- Real bank data ends mid-month, so the report now defaults to the last whole month (`finance/report.py`).
- Card spending counts when charged; the card payment from checking is excluded as a transfer.
