# Live finance dashboard

The dashboard, purchase calculator, and four-file upload dialog use the Python
finance API. Canned finance data is no longer used by the live interface. Agent
chat and written reports use Strands when AI provider access is configured.
Without credentials, the financial calculations continue to work and chat is disabled.

## Accounts first

Private finance and Plaid endpoints now require sign-in and a selected company. Complete [Supabase setup](accounts.md) first. Visitors may choose **Try the demo** without credentials.

## Setup

Use Python 3.12 and Node.js (validated with Node 24). From the repository root:

```bash
bash scripts/setup_backend.sh
cd frontend
npm ci
```

On Windows, create the environment from the repository root instead:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements/backend-bootstrap.txt
cd frontend
npm ci
```

## Start development in two terminals

For optional AI features, copy `backend/.env.example` to `backend/.env` only if
that file does not already exist. Set `ANTHROPIC_API_KEY` locally and verify your
configured model IDs are accessible to your account. `MODEL_PROVIDER=bedrock`
uses AWS instead; see the example file and agents README. Never commit secrets.
Restart the API after changing configuration. No model credentials are needed
for the dashboard, purchase calculator, or uploads.

In terminal one, from the repository root:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows, use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

In terminal two:

```bash
cd frontend
npm run dev
```

Use the address printed by Vite to open the app in your local browser. Vite
forwards `/api` requests to port 8000, so both terminals must remain running.

To run the built frontend and API from one process, build first:

```bash
cd frontend
npm run build
cd ..
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

FastAPI detects `frontend/dist` at startup and serves the built application there.
Restart the API after the first build if it was already running without that
directory. Use one backend worker for consistent temporary AI chat history. Saved books and bank connections live in Supabase.

## Verify the complete flow

1. Choose **Try the demo**. September should show $45,070 received, $52,900 spent, and a $7,830 loss.
   The $15,000 purchase fails the one-month reserve policy.
2. Select August. Monthly profit should be $15,000. Cash and receivables retain
   their labeled September 30 snapshot date.
3. Return to welcome, create/sign in to an account, and create a company. It opens at
   **Add your financial records**, with a progress bar along the bottom.
4. Add records. This step needs AI credentials. Either choose **Use the sample contractor bank**
   (or **Connect a bank** for the Plaid window), or add the CSV exports in `test-data/imports`
   and choose **Read 6 files**. The review step lists what each file was read as, skips
   `crew_contacts.csv`, and asks for details the files did not supply. Text or out-of-range
   values in those fields are rejected. Nothing is saved until **Save and open my dashboard**.
   The badge then reads **Your books**.
5. The four-file sets in `test-data/uploads` are no longer selectable in the browser. They
   still load through `POST /api/upload` (see [accounts.md](accounts.md) for an authenticated
   example) and are what the browser tests seed. Through that endpoint, `02-higher-insurance`
   gives $53,140 expenses, an $8,070 loss, and a $16,903 purchase shortfall, and
   `03-invalid-invoices` is rejected with the previous books kept.
6. Open the gear menu, choose **Clear company books**, and confirm. The company returns to
   **Add your financial records**. Switch company and choose **Try the demo** to see the fictional books.

With provider credentials configured, also check that the written report loads
and chat answers a question such as "How much did I spend in September?".
After new records are saved, chat should use the new figures and
start a new conversation. Another browser starts at welcome and can open its own account or the public demo. Signing into the same account reopens the saved books.
If the provider fails, the UI should show an error and leave the dashboard usable.

Uploads replace the selected company’s saved books. Files are validated together,
encoded into a server-encrypted snapshot, and persisted in Supabase. A backend
restart retains these books and imported sources; AI conversation/report caches
are temporary and may be evicted. Separate accounts have separate companies.

## Automated checks

From the repository root:

```bash
.venv/bin/python -m pytest backend/tests -q
```

From `frontend`, with both development-server ports free:

```bash
npx playwright install chromium
npm run test:e2e
npm run build
```

The browser suite starts and stops its own API and Vite processes using an explicit offline Supabase provider fixture. It does not create real Supabase users. It tests live
month selection, purchase checks, upload recalculation, session isolation,
rejected uploads, company clearing, account signup/login/logout, and report request errors. With an existing
Chromium install, set `TOOLBELT_CHROMIUM_PATH` to its executable instead of
downloading Playwright's browser. `TOOLBELT_TEST_PYTHON` can select a different
Python environment; otherwise the suite uses the repository's `.venv`.

Offline backend tests exercise streamed agents with fake model responses,
including simultaneous browsers and tool threads. Browser tests use the real
finance API and controlled AI event streams to check narrative rendering, chat
cards, follow-ups, history reset, and provider errors. The suite disables real
Anthropic calls in its server process, even if your local key is configured.

Real model checks are opt-in, require provider access, and incur model charges:

```bash
RUN_LIVE_TESTS=1 .venv/bin/python -m pytest backend/tests/test_agents_live.py -v
```

## HTTP contract

| Route | Behavior |
| --- | --- |
| `GET /api/health` | Returns `{"status":"ok"}` |
| `GET /api/report?month=YYYY-MM` | Complete report; month defaults to the last whole month |
| `GET /api/report/narrative?month=YYYY-MM` | Streamed AI written report for the selected company’s books |
| `POST /api/ask` | JSON `question`, optional `session_id` and `month`; streamed AI response |
| `GET /api/affordability?amount=15000` | Active books and the last complete month's reserve |
| `POST /api/upload` | Multipart field `files`, repeated once per required file; returns the new report |
| `POST /api/reset` | Clears the selected company’s saved books, imports, and stored bank connections |

All private routes require HTTP-only account cookies (or an authenticated Bearer token)
and `X-Company-ID`. Anonymous access returns **401**, missing company selection
returns **409**, and a company you do not own returns **404**. Empty companies
return `{has_books: false, company: ...}` from `/api/report`.

Public `/api/demo/report` and `/api/demo/affordability` expose only fictional data.

Report metadata includes `month`, available `months`, `previous_summary`,
`is_sample`, `dataset_revision`, and `agent_status`, followed by the existing finance result
objects. `agent_status.available` indicates configuration, not verified model access.
`narrative` remains `null`; written text comes from the separate stream. Months cover the
opening-balance/as-of window, including months with no transactions. Purchases
always use snapshot cash, regardless of the selected report month.

Invalid dates, amounts, months, or file contents return **422**. Files exceeding
10 MiB return **413**. Validation errors have a human-readable `detail`;
missing-parameter errors use FastAPI's standard validation list. State changes
only after validation and complete report construction succeed. Requests retain
HTTP-only, same-origin account cookies through Vite’s proxy.

Agents use a request-local books context copied into Strands tool threads.
Written-report caches and chat sessions belong to each company/dataset revision. A valid upload creates fresh AI state; rejected uploads preserve
it. Chat retains at most 32 conversations per dataset. Streaming failures emit an
error and completion event instead of leaving the UI waiting indefinitely.
