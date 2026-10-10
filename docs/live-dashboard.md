# Live finance dashboard

The dashboard, purchase calculator, and four-file upload dialog use the Python
finance API. Canned finance data is no longer used by the live interface. Agent
chat and AI narratives remain unconnected and are labeled accordingly.

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
directory. Use one backend worker: uploaded datasets are stored in process memory.

## Verify the complete flow

1. September should show $45,070 received, $52,900 spent, and a $7,830 loss.
   The $15,000 purchase fails the one-month reserve policy.
2. Select August. Monthly profit should be $15,000. Cash and receivables retain
   their labeled September 30 snapshot date.
3. Copy the four sample files from `backend/app/data/sample` to a separate
   directory. In that copy's `transactions.csv`, change September insurance
   from `-1260` to `-1500`.
4. Choose **Use your own books**, select the four files, and submit. Expenses
   become $53,140 and loss $8,070. The purchase shortfall becomes $16,903. The
   badge changes from **Sample data** to **Your books**.
5. Try uploading an invoices file without required columns. The dialog should
   report the error, remain open, and retain the previous books.
6. To restore the sample, open the upload dialog and choose **Use sample books**.

Uploads replace only this browser session's books; another browser starts with
the sample. Sessions expire after an hour of inactivity and can be evicted when
the bounded 16-session store is full. A backend restart restores sample data.
Files are validated together and are not saved to disk. This is a local
development/demo workflow; account login and durable storage are not implemented.

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

The browser suite starts and stops its own API and Vite processes. It tests live
month selection, purchase checks, upload recalculation, session isolation,
rejected uploads, sample reset, and report request errors. With an existing
Chromium install, set `TOOLBELT_CHROMIUM_PATH` to its executable instead of
downloading Playwright's browser. `TOOLBELT_TEST_PYTHON` can select a different
Python environment; otherwise the suite uses the repository's `.venv`.

## HTTP contract

| Route | Behavior |
| --- | --- |
| `GET /api/health` | Returns `{"status":"ok"}` |
| `GET /api/report?month=YYYY-MM` | Complete report; month defaults to the as-of month |
| `GET /api/affordability?amount=15000` | Active books and the last complete month's reserve |
| `POST /api/upload` | Multipart field `files`, repeated once per required file; returns the new report |
| `POST /api/reset` | Restores sample books and clears the current browser's dataset cookie |

Report metadata includes `month`, available `months`, `previous_summary`,
`is_sample`, and `dataset_revision`, followed by the existing finance result
objects. `narrative` is `null` until agent integration. Months cover the
opening-balance/as-of window, including months with no transactions. Purchases
always use snapshot cash, regardless of the selected report month.

Invalid dates, amounts, months, or file contents return **422**. Files exceeding
10 MiB return **413**. Validation errors have a human-readable `detail`;
missing-parameter errors use FastAPI's standard validation list. State changes
only after validation and complete report construction succeed. Requests retain
an HTTP-only, same-origin dataset cookie through Vite's proxy.

Aidan's agent integration should use the active `Books` snapshot from the same
dataset store. Narrative and ask endpoints are left for that work; no model
provider, credentials, or model ID is assumed by this section.
