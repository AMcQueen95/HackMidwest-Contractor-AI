# Accounts, companies, and saved books

The application on `main` provides email/password sign-up, sign-in, confirmation,
password recovery, logout, company selection/creation, and Supabase-backed storage.
It is based on main's CSV/Plaid integration. All finance, import, and Plaid routes
require a verified account and a company owned by that account. Visitors can use
the read-only fictional demo without signing in; it does not run AI or connect banks.

## 1. Create the database tables

For the team's new Supabase project, open:

1. Supabase Dashboard → project `gumllvaagirfmknmyplp` → **SQL Editor**.
2. Click **New query**.
3. Open [`backend/migrations/001_accounts.sql`](../backend/migrations/001_accounts.sql)
   in VS Code. Copy the full file and paste it into the query.
4. Click **Run**. Expect **Success. No rows returned**.
5. Open **Table Editor**. Confirm `profiles`, `companies`, and `company_state` exist.

The migration is transactional and can be rerun on this schema. It is intended
for a fresh project; review existing tables and policies before using it in another
database. It creates owner-only row-level security (RLS) and a profile trigger for
new and existing Supabase Auth users. Passwords are handled by Supabase Auth.

## 2. Configure email confirmation and redirects

In Supabase **Authentication**:

- Under **URL Configuration**, set **Site URL** to `http://localhost:5173` for local
  development and add that exact URL to **Redirect URLs**. If you use `127.0.0.1`
  instead, add `http://127.0.0.1:5173` and use that host consistently.
- Keep email/password sign-in enabled. Keep **Confirm email** enabled for real users.
- Set the password minimum to at least 12 characters to match the app.
- Before a public release, configure SMTP/email delivery and test confirmation and
  password-reset emails. Supabase's built-in sender has restrictions and rate limits;
  do not assume it can deliver to every user.

Confirmation/recovery links establish a session through `/api/auth/session`;
URL-fragment tokens are removed before the account request. Successful password
recovery shows **Choose a new password**. Tokens are kept in HTTP-only cookies,
not localStorage. The public demo needs none of these settings.

## 3. Configure your backend locally

In VS Code, open the repository folder. Open `backend/.env`. If it does not exist,
copy `backend/.env.example` to `backend/.env`; preserve any existing AI/Plaid keys.

Set:

```dotenv
SUPABASE_URL=https://gumllvaagirfmknmyplp.supabase.co
SUPABASE_PUBLISHABLE_KEY=your_publishable_key_from_the_Connect_dialog
PUBLIC_APP_URL=http://localhost:5173
COOKIE_SECURE=false
APP_DATA_KEY=your_generated_server_encryption_key
```

The Supabase publishable key is designed to be public. A legacy **anon** key also
works via `SUPABASE_ANON_KEY`. This application does not need a **secret** key,
**service-role** key, or database password. Do not put privileged keys in frontend
code or a `VITE_*` variable.

After installing dependencies, generate the encryption key on your own computer
from a terminal at the repository root:

```bash
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

On Windows, substitute `.venv\Scripts\python.exe`. Copy that local output into
`APP_DATA_KEY`. Keep it stable and backed up securely. Every server using the same
database needs the same key; losing or replacing it makes saved books and Plaid
tokens unreadable. Never commit it. `.env` files are gitignored. The cloud checkout
has its own local configuration; Git does not transfer that file to your Mac.

## 4. Install and start (Mac)

From the repository root:

```bash
git fetch origin
git switch main
git pull --ff-only
bash scripts/setup_backend.sh
.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Use Python 3.12 for that setup script. In a **second terminal**:

```bash
cd frontend
npm ci
npm run dev
```

Use the address Vite prints in your local browser. Leave both terminals running.
Use **Control+C** to stop a server. Control+Z suspends it and can leave its port
occupied. Restart the backend whenever you change `backend/.env`.

## 5. Check accounts and persistence manually

1. The first page should show sign-in, account creation, and **Try the demo**.
2. Choose **Create account**, enter your email and a password of at least 12
   characters. If confirmation is enabled, follow the email link before signing in.
3. Create a company. Expect the **Add your financial records** step.
4. Add records with **Use the sample contractor bank** or the CSV exports in
   `test-data/imports` (both need AI credentials), review, and save. To load the exact
   four-file set instead, send `test-data/uploads/01-baseline` to `POST /api/upload`;
   September expenses should then be **$52,900** and profit **−$7,830**.
5. Sign out. Open a private/incognito window, sign in as the same account, and
   select the company. Those books should still appear.
6. Stop and restart the backend. Sign in/select the company again. Books should
   remain. AI conversations and cached narratives may reset.
7. Create a second account. Its company list should be empty, and new companies
   should have no books. Knowing the first company's ID must not grant access.
8. Send `02-higher-insurance` to `POST /api/upload` for the first company. Expenses become
   **$53,140**. Send `03-invalid-invoices`; expect a 422 error and unchanged prior books.
9. In the gear menu choose **Clear company books** and confirm. It becomes empty; the
   separate demo still works.
10. Check **Forgot password?**, email delivery, the reset link, and signing in with
    the new password. Confirm the old password fails.

For direct API checks, use a terminal cookie jar (not a tracked file). Example:

```bash
curl -i http://127.0.0.1:8000/api/plaid/status
# Expected: 401, because no user is signed in.
```

Authenticated requests need the cookies set by `/api/auth/login` and
`X-Company-ID: <id from /api/auth/me or POST /api/companies>`. API clients may
instead use the user's `Authorization: Bearer <access_token>` plus that company
header. Never use a service-role token. A legacy `toolbelt_session` cookie does
not establish account ownership. Frontend code in `src/api/index.js` adds the
selected company header and refreshes expiring sessions automatically.

## HTTP behavior and teammate integration

| Route | Result |
| --- | --- |
| `GET /api/auth/config` | Whether the backend has Supabase configuration |
| `POST /api/auth/signup` | `{email, password}`; sets cookies if confirmed, otherwise asks the user to confirm |
| `POST /api/auth/login` | `{email, password}`; sets HTTP-only cookies, returns public user details |
| `POST /api/auth/refresh` | Uses HTTP-only refresh cookie; rotates session cookies |
| `POST /api/auth/logout` | Ends provider session when reachable; always clears browser account cookies |
| `POST /api/auth/recover` | `{email}`; generic response, provider sends reset email |
| `POST /api/auth/password` | Authenticated `{password}` update |
| `GET /api/auth/me` | Public user details and their companies |
| `POST /api/companies` | Authenticated `{name}`; server assigns the owner |
| `GET /api/report` | Requires company; `{has_books:false, company, agent_status}` when empty |
| `GET /api/demo/report`, `GET /api/demo/affordability` | Public fictional math only |

All other finance/import/Plaid routes are protected. Anonymous requests return
**401**; no selected company returns **409**; a company you do not own returns
**404**. Validation returns **422**, upload limits **413**. A simultaneous write
can return **409** rather than overwrite another request. Refresh and retry that
write. Database writes finish before success is returned to the caller.

Tyler can polish `AccountGate.jsx` without changing the API contract. Its child
`App` mounts only after company selection or explicit demo entry; switching
companies remounts it and clears displayed prior-company data. Keep demo uploads
and AI disabled. Aidan's CSV/Plaid endpoints receive the same account boundary;
Plaid Link uses a stable account/company identity. Bank access tokens are never
sent to the frontend. Plaid retrieves transactions/balances, not invoice documents.

## Deployment and limits

Serve the frontend and `/api` on one browser origin: a FastAPI deployment can serve
`frontend/dist`, or a frontend host can proxy `/api` to the backend. Set the real
HTTPS app URL in `PUBLIC_APP_URL`, Supabase Site URL/redirect allowlist, and
`COOKIE_SECURE=true`. A separate frontend origin without a proxy is not configured
by this change. The backend needs its secrets in the hosting platform's environment
settings. Netlify alone does not run this Python server.

Books, normalized imports, and bank tokens live in server-encrypted Supabase
snapshots. The backend uses the public key plus the **user's JWT**, so RLS applies.
No service-role bypass is used. Database RLS is the access boundary; encryption
also keeps stored finance/token payloads unreadable without the server key.

Use one backend worker for consistent temporary AI history. This version supports
owner accounts and multiple companies, not invited teammates or company roles.
Before production, add operational backups/key management, monitoring, AI budget
and upload limits appropriate to your audience, and a Plaid disconnect/revocation
flow. Clearing stored bank tokens does not revoke the Plaid item itself. Live
model access, bank access, SMTP delivery, and hosted HTTPS require separate checks.

## Automated verification and troubleshooting

```bash
.venv/bin/python -m pytest backend/tests -q
cd frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests own ports 8000/5173 and use an explicit offline Supabase provider.
They exercise the real account routes, guard, encryption, storage adapter and
finance math without creating real users or making paid model calls. Offline
tests do not establish that the migration was applied to your live database.

- **Sign-in is being set up:** configure URL/public key and restart the backend.
- **Check the database migration:** run the SQL and verify the three tables exist.
- **Financial storage encryption is not configured:** generate/set `APP_DATA_KEY`.
- **Saved records could not be read:** restore the encryption key used to save them.
- **Email/password incorrect or unconfirmed:** check confirmation and try recovery.
- **Email doesn't arrive:** check Auth email/SMTP settings and provider rate limits.
- **Address already in use:** stop your existing backend with Control+C.
- **Requests must come from the app:** match `PUBLIC_APP_URL` to the browser origin.
- **Cloud requests are blocked:** review/save the prepared environment network
  addition for `gumllvaagirfmknmyplp.supabase.co`, then publish the environment.
  A saved draft alone does not change the running machine's network policy.
