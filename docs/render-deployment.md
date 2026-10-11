# Deploy Toolbelt CFO to Render

Use **one Docker Web Service** for both the React site and the FastAPI API.
The Dockerfile builds React with Node 24, installs Python 3.12 dependencies,
and runs one Uvicorn worker on Render's `PORT`. FastAPI serves `frontend/dist`
and `/api` from the same HTTPS address. Supabase keeps the saved company data;
the application does not require a persistent local disk.

## Why visitors won't receive your AI keys

The browser sends requests to your own `/api` routes. The Python server calls
Anthropic and Plaid with credentials stored in Render's **Environment** settings.
Credentials are not supplied to the frontend build. `.dockerignore` excludes
local `.env` files and `.git` from the image build context. The Dockerfile has
no credential build arguments or hardcoded keys.

Never put AI, Plaid, encryption or service-role keys in React code, `VITE_`
variables, `render.yaml`, a Docker build argument, or a committed `.env`.
The Supabase publishable key is designed to be public; it is not an AI key or
service-role credential. This application still keeps its configuration on
the server and uses the signed-in user's JWT for database access.

Server-side secrets prevent shipping credentials to browsers. They do not
prevent a signed-in user from using your AI endpoints and consuming your
provider budget. Set provider spending limits and add per-user request limits
before broad public use. Do not log credentials or financial request bodies.
If a secret has previously been committed or exposed, rotate it at the provider;
moving it into Render does not undo an earlier exposure.

## 1. Create the Render service

1. Sign in to Render and connect your GitHub account **PBoekhout**. Grant access
   to `AMcQueen95/HackMidwest-Contractor-AI` if Render cannot list it. An owner
   of the repository may need to approve installation access.
2. Choose **New → Web Service** and select that repository.
3. Select branch **`render-deployment`**, which contains these deployment files
   and the app from main at commit `f6e61cb`. After the team merges the deployment
   files, you can select `main` and update the Blueprint branch accordingly.
4. Select the **Docker** runtime. Leave Root Directory empty; the Dockerfile
   is `./Dockerfile` and its build context is the repository root. Use the
   Dockerfile's command rather than overriding it with a development server.
5. Set the health check path to **`/api/health`**.
6. Choose the service plan shown in your dashboard. A free plan is suitable
   for a first demo if available, but idle services can sleep and the first
   request may be slow. Review Render's current limits and price before
   choosing a paid plan. AI provider usage is separate from hosting charges.
7. Keep automatic deploys off for the first setup. You can enable them after
   the team has agreed which branch is the deployment source.

An optional `render.yaml` Blueprint expresses the same settings and prompts for
environment values without putting them in Git. Creating a Web Service manually
as above is enough; you do not need to create both services.

## 2. Add the server environment variables

In Render's **Environment** section, enter these values securely. Copy values
directly from your local configuration/provider dashboard; do not paste secret
values in chat, screenshots, source control or terminal commands.

| Name | Value to enter |
| --- | --- |
| `SUPABASE_URL` | Your existing Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Your project's publishable key; do not use a service-role key |
| `APP_DATA_KEY` | **The same encryption key your local backend already uses** if using the same Supabase database |
| `PUBLIC_APP_URL` | The exact Render HTTPS URL, e.g. `https://your-service.onrender.com`, with no path |
| `COOKIE_SECURE` | `true` |
| `MODEL_PROVIDER` | `anthropic`, if using your existing Anthropic setup |
| `ANTHROPIC_API_KEY` | Your existing working Anthropic key |
| `CFO_MODEL_ID` | Your currently working CFO model ID, if you customized it locally |
| `SPECIALIST_MODEL_ID` | Your currently working specialist model ID, if customized locally |

**Do not generate a different `APP_DATA_KEY` for the same database.** Existing
company books and Plaid tokens are encrypted with your current key. Reusing it
lets Render read existing companies. Keep a secure backup and keep the value
stable across deploys. A fresh database can use a separately generated key.

For Plaid testing, also add these from your working local setup:

| Name | Value to enter |
| --- | --- |
| `PLAID_ENV` | `sandbox` |
| `PLAID_CLIENT_ID` | Your Plaid client ID |
| `PLAID_SECRET` | Your Plaid sandbox secret |
| `PLAID_SANDBOX_ACCESS_TOKEN` | The saved test-bank token, only if using the sample-bank button |
| `PLAID_SANDBOX_ITEM_ID` | Its saved item ID, only if using the sample-bank button |

Do not run the sandbox creation script on every build or restart. The saved
test-bank token is reused. Real bank connections require Plaid production
approval/configuration; setting the environment to production alone is insufficient.

If the service URL isn't known during creation, deploy first, copy its assigned
HTTPS URL, then set `PUBLIC_APP_URL` and redeploy before testing account links.
Do not keep `http://localhost:5174` as Render's public URL. This changes the hosted
service only; your local backend can retain its localhost URL.

## 3. Update Supabase redirects

In your existing Supabase project, open **Authentication → URL Configuration**:

1. Set **Site URL** to the Render HTTPS address.
2. Add that exact address to **Redirect URLs**. Include a trailing-slash variant
   if needed by the links you use. Add your custom domain too if you later use one.
3. Keep `http://localhost:5174` in Redirect URLs if you want to continue local testing.
4. Save the changes. Check the auth email settings/SMTP if confirmation or recovery
   emails don't arrive.

The existing database migration only needs to be applied once per Supabase
project. If you reuse your current project and tables, don't recreate them.

## 4. Deploy and test the hosted application

Start the deployment and watch Render's build/start logs. The expected flow is
React build → Python dependency installation → Uvicorn listening on Render's
port. The build/start logs should never print environment variable values.

Once Render marks it live:

1. Open `https://your-service.onrender.com/api/health`. Expect `{"status":"ok"}`.
2. Open the root address in a private browser window. The welcome page and
   read-only demo should work without signing in. Anonymous private finance
   API requests should return 401.
3. Create/sign in to an account. Test a confirmation email and a password-reset
   link: both should return to the hosted app, not localhost.
4. Create a test company, choose its trades, upload your baseline CSVs, review
   and save. Check dashboard figures, month selection and the hiring/purchase
   checks. Ask one CFO question to test live model access and streaming.
5. Sign out and back in. Confirm the company, trade choices and uploaded books
   remain. Trigger a service restart and verify them again. Temporary chat
   history may reset; saved company records should persist.
6. Use a second account and confirm it cannot access the first account's company.
7. Test the Plaid sandbox flow if configured. Confirm you can revisit the saved
   company without recreating the sample bank.
8. In browser developer tools, inspect Network requests and downloaded JavaScript.
   AI/Plaid secret keys and `APP_DATA_KEY` must not appear in responses or assets.
   Normal user session data and Plaid **public/link tokens** have separate purposes;
   those are not your provider secret or Plaid access token.

The local build/smoke checks validate serving the production bundle and private
route protection without live provider calls. They do not establish that Render
has deployed, that hosted email redirects work, or that live AI/Plaid access works.

Validation of this branch against main `f6e61cb`: **206 backend tests passed,
10 opt-in live-provider tests skipped**, React production build passed, and a
non-root Docker container passed health, HTML/assets, demo, anonymous access,
HTTPS-origin and source/environment-file protection checks on `PORT=10000`.
No configured server secret values were found in the local browser bundle or
deployment files. For the cloud-only Docker check, package installation used
temporary mounts of this environment's trusted proxy CA bundle; TLS verification
stayed enabled and those certificates/settings are absent from the final image.
The committed Dockerfile uses normal public certificate trust for Render.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Build can't find the Dockerfile | Branch `render-deployment`, empty Root Directory, Dockerfile path `./Dockerfile` |
| Service can't detect a port | Use the Dockerfile's command; bind `0.0.0.0` and Render's `PORT`, not localhost |
| Root page returns 404 | The frontend build must finish and `frontend/dist` must be copied into the final image |
| “This request must come from the app” | `PUBLIC_APP_URL` must exactly match the HTTPS browser origin |
| Saved records can't be read | Restore the original `APP_DATA_KEY`; don't clear records to fix a missing key |
| Sign-in or reset links go to localhost | Fix `PUBLIC_APP_URL` and Supabase Site URL/Redirect URLs, then retry a fresh email |
| Dashboard works but AI fails | Check provider/model access, billing and environment configuration; do not expose the key for diagnosis |
| First load is slow | Free-service cold start can delay the first request; check current Render plan behavior |

Docker's forwarded-header trust is configured for Render's ingress. If you reuse
this container on another host that permits direct untrusted connections, restrict
trusted proxy addresses for that host.

Render reference pages: [Docker services](https://render.com/docs/docker),
[environment variables](https://render.com/docs/configure-environment-variables),
[FastAPI deployment](https://render.com/docs/deploy-fastapi),
[free services](https://render.com/docs/free).
