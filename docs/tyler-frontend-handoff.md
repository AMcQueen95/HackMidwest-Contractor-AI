# Toolbelt CFO — frontend handoff for Tyler and his AI

This document scopes the next frontend work after account sign-in and company
storage are integrated. The current setup and API contracts are in
[accounts.md](accounts.md), [live-dashboard.md](live-dashboard.md), and
[imports.md](imports.md).
Give this entire document to your AI along with access to the repository.

Repository: https://github.com/AMcQueen95/HackMidwest-Contractor-AI

The account implementation is merged into `main` alongside Aidan’s saved Plaid
sandbox integration. Inspect the latest `main`, repository instructions, and
current changes before coding; the team may have added more work. Work on a frontend feature branch and submit a PR into main.
Preserve teammates' changes and coordinate before changing API contracts.

## Goal

Make the website feel polished and easy for a contractor to use. The frontend
is what we most want to showcase. Visitors should start at a welcome page,
choose a demo or their own company, and reach a clear financial dashboard.

Keep the Ridgeline sample company as an explicit demo. A new user's company
should start empty, without being populated with sample numbers.

## Team ownership

| Owner | Responsibility |
| --- | --- |
| Tyler and his AI | Visual design, navigation, onboarding screens, company selection, upload/review screens, dashboard polish, responsive behavior, and browser checks |
| Aidan | Flexible document ingestion, extraction agent, and existing CFO/specialist agents |
| Palmer and backend work | Authentication integration, company ownership checks, persistent records/storage, validation, duplicate handling, and API support |
| Whole team | Agree on required record fields, API shapes, supported formats, demo isolation, and acceptance examples |

Supabase Auth and Postgres are integrated. The project has profiles, companies,
and encrypted company snapshots with owner-only row-level security. Raw document
storage, team invitations, and company membership roles remain separate work.
Render is a proposed hosting direction; deployment is still separate work.

## Existing working application

- React 19, JavaScript, Vite, Recharts, plain CSS, and light/dark themes.
- A Python FastAPI backend with real finance calculations.
- Live dashboard, month selection, purchase calculator, and four-file upload.
- Streamed CFO chat and written reports when AI credentials are configured.
- Email/password signup/login, confirmation, password recovery, and logout.
- Owner-only company directory and creation; new companies start empty.
- Books, CSV import sources and Plaid tokens persist in encrypted database snapshots.
- Temporary AI history/cache belongs to the company/dataset revision.
- Agent-assisted arbitrary CSV imports and saved Plaid sandbox connections are
  backend endpoints; their frontend controls and general document support remain work.

The merged application passed 160 offline backend tests and nine browser tests. Live-model/Plaid tests are opt-in
and skipped by default. Browser Auth uses an explicit offline provider fixture;
browser AI uses controlled event responses. These do not prove live model access.

## Intended user journey

1. **Welcome:** Explain Toolbelt CFO in plain language. Show Sign in, Create
   account, and Try the demo. Do not load financial records or start an AI
   narrative just because someone opens this page.
2. **Sign in/create account:** Use the agreed authentication provider. Include
   validation, loading, failure, email-verification, and password-reset states.
3. **Choose a company:** Show only companies the account belongs to. Allow
   creation of a company and show the current company clearly in navigation.
4. **New company:** Show an empty dashboard with Upload financial records as
   the main action. Explain that records are needed to calculate results.
5. **Upload:** Select a supported file, then show upload and processing progress.
6. **Review:** Present extracted records, uncertain fields, missing information,
   validation errors, and duplicate warnings. Let users correct or cancel before
   confirming an import. Final validation and saving happen in the backend.
7. **Dashboard:** Show confirmed finance results, issues, purchase checks, and
   CFO chat for the active company and reporting period.
8. **Return visit:** After signing back in, owned companies and confirmed
   records persist through the implemented database storage.

Tyler can polish the existing account/company screens and add CSV/Plaid controls
using the current APIs. Upload review/general-document extraction still needs
agreed contracts; label previews clearly. Keep working finance integration intact.

## Demo behavior

- Try the demo opens a clearly labeled fictional Ridgeline company.
- Demo access should not require an account.
- Provide a clear route back to the welcome page or to create a real company.
- Keep demo records separate from real company records. Switching to the demo
  must not discard uploaded books, overwrite a company, or reuse its AI history.
- Use the existing public `/api/demo/report` and `/api/demo/affordability` routes
  via `setWorkspace({demo:true, companyId:null})`. Switching demo/company remounts
  the dashboard. `/api/reset` clears company books; never use it as a demo switch.
- Public demo AI is disabled; private AI routes require account/company access.

## Visual direction

Use strong visual hierarchy: company and reporting period first, then revenue,
expenses, profit/loss, and available cash. Make the most useful figures easy to
read at a glance. Use distinct spacing, readable type, consistent buttons, and
clear primary actions. Color can reinforce profit/loss but should not carry the
meaning alone. Keep contractor-facing language simple and concrete.

Retain the useful existing sections: receivables, expense changes, job profit,
recurring bills, purchase affordability, and CFO advice. Keep tables and chat
usable on phones, avoid page-wide horizontal overflow, and preserve keyboard
navigation, visible focus, labeled inputs, and readable contrast in both themes.

Every screen needs an appropriate loading, empty, success, and error state.
AI failure must leave the financial dashboard usable. Financial figures come
from the backend, not calculations or invented values in React.

## Flexible-upload expectations

The team wants to move beyond four files to one document containing financial
records. Aidan is responsible for extraction and normalization. Start with an
agreed supported-format list, such as CSV/JSON, then Excel and text-based PDFs.
Scanned PDFs/images need OCR and may follow later. Avoid promising all file
types before the backend supports them.

For Google Docs, exporting a supported document and uploading it is the first
option. Direct Google Docs/Sheets access requires a later authorization flow;
Google sign-in alone does not grant document access. Do not show a connected
Google integration as working until that capability exists.

An expense-only document may support expense charts without establishing
revenue, profit, cash, or receivables. Show missing metrics as unavailable with
a useful explanation, rather than zero. Ask for missing information without
guessing it. Confirm supported size limits and rejection messages with Aidan.

## Existing backend contracts — preserve these

All frontend HTTP calls live in `frontend/src/api/index.js`. Development Vite
proxies `/api` to the backend; production currently serves the built frontend
from FastAPI. Existing requests use same-origin cookies.

| Endpoint | Existing behavior |
| --- | --- |
| `GET /api/health` | Health response |
| `GET /api/report?month=YYYY-MM` | Complete report for the selected company; `has_books:false` when empty |
| `GET /api/report/narrative?month=YYYY-MM` | Streamed written report |
| `GET /api/affordability?amount=15000` | Purchase calculation from the active books |
| `POST /api/ask` | JSON `question`, optional `session_id` and `month`; streamed answer |
| `POST /api/upload` | Four multipart fields named `files`, one per required filename; returns the new report |
| `POST /api/reset` | Clears the selected company’s books, import sources, and saved bank tokens |

The current upload requires `transactions.csv`, `jobs.csv`, `invoices.csv`, and
`business.json`, each at most 10 MiB. Invalid input returns 422; oversized files
return 413. Rejected uploads preserve the previous dataset.

Report metadata includes `business`, `month`, `months`, `previous_summary`,
`is_sample`, `dataset_revision`, and `agent_status`. The report also includes
the existing finance result objects. `agent_status.available` means provider
configuration exists, not that a model call is guaranteed to succeed.

Narrative SSE events are `text`, `reset`, `error`, and `done`. Chat SSE events
have `type` values `session`, `status`, `text`, `text_reset`, `card`, `error`,
and `done`. Preserve the parser and card rendering. Error/completion events
must end loading states. Abort requests and clear stale report/chat state when
the active company, dataset, or reporting period changes.

Cash and receivables are as-of snapshots; changing the monthly report does not
change their snapshot date. Keep those dates visible. Purchase checks use
snapshot cash and the finance reserve policy.

Auth and company APIs are implemented; see [accounts.md](accounts.md). All private
finance/import/Plaid requests need HTTP-only account cookies plus `X-Company-ID`;
`src/api/index.js` adds the selected company and refreshes expiring sessions.
The backend verifies company ownership on every request. See [imports.md](imports.md)
for CSV/Plaid endpoints and saved sandbox setup. An editable import-review workflow
is future work; agree its request/response shapes before presenting it as operational.

## Useful files and startup

- `frontend/src/components/AccountGate.jsx`: welcome, authentication, company selection.
- `frontend/src/App.jsx`: report state, empty company, AI narrative.
- `frontend/src/components/`: Header, UploadDialog, ChatWidget, cards, charts.
- `frontend/src/styles.css`: shared styling.
- `frontend/src/api/index.js`: HTTP calls and SSE handling.
- `frontend/tests/browser/finance.spec.js`: existing browser checks.
- `docs/live-dashboard.md`: complete startup/testing instructions.
- `test-data/uploads/`: baseline, higher-insurance, and invalid-invoice examples.
- `backend/.env.example`: provider configuration names; never commit real keys.

Use Python 3.12 and Node 24. On Mac/Linux, from the repository root, prepare (complete [Supabase/env setup](accounts.md) before private-company checks):

```bash
bash scripts/setup_backend.sh
cd frontend
npm ci
```

Start the API in one terminal from the repository root:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal from the repository root:

```bash
cd frontend
npm run dev
```

Open the address Vite prints in your local browser. Use Control+C to stop a
server; Control+Z only suspends it and leaves the port occupied. API keys belong
in the backend environment, never React code or a `VITE_` variable.

## Delivery order and acceptance

First agree a small screen/navigation plan and API needs with the team. Build
the welcome page, explicit demo entry, and dashboard polish while preserving
the existing API. Keep the implemented authentication/company navigation intact, then add CSV/Plaid
controls, review, and import completion as those contracts are agreed.

The working account milestone is: create an account/company, upload the four
canonical files, see calculated results, sign out/back in, and reopen saved books.
The next milestone is one CSV/Plaid entry through the UI, followed by review and
confirmation when the backend supports that workflow.

For each PR, describe what works against real APIs, what is a preview, any
backend dependencies, and the checks run. Keep teammates' work and financial
contracts intact. Update browser tests when navigation changes instead of
removing the underlying upload, isolation, failure, and chat assertions.

Before handoff, verify the production build and relevant browser tests:

```bash
# Run from frontend. Stop your own API/Vite servers first to free test ports.
npx playwright install chromium
npm run test:e2e
npm run build
```

Check desktop/mobile layouts, both themes, company switching, demo separation,
empty companies, rejected imports, missing metrics, and AI unavailable/error
states. The website should make real progress and incomplete capabilities
equally clear to the user.
