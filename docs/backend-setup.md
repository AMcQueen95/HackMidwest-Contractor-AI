# Python backend setup

This prepares the Python backend stack described in the project README. It does
not implement the application. The dependency versions were validated together
with Python 3.12 on Linux x86_64.

## Install and validate

Install Python 3.12 with its `venv` module, then run from the checkout:

```bash
bash scripts/setup_backend.sh
source .venv/bin/activate
```

The setup script creates an ignored `.venv`, installs the pinned bootstrap
requirements, checks dependency compatibility, and runs a functional stack check.
Rerunning it reuses the environment and installed packages. It does not edit
application files or dependency declarations.

The stack includes FastAPI, Uvicorn, pandas, the Strands Agents SDK, pytest, httpx,
and multipart upload support. The bootstrap requirements pin their dependencies
too; they are an environment baseline for the planned backend.

## What validation covers

```bash
python -m pip --cache-dir .venv/pip-cache check
python scripts/validate_backend_stack.py
python -m pytest --version
```

The stack check starts a temporary local Uvicorn server, uploads a CSV through
FastAPI, invokes a Strands tool that calculates its net amount using pandas, and
checks the returned value is `750`. It also verifies the OpenAPI schema and stops
the server before exiting. This validates installed prerequisites; it does not
validate the Toolbelt CFO application or call a model.

`pytest --version` only confirms the test runner is installed. Validate the data
and finance component with its actual tests and handoff script:

```bash
python -m pytest backend/tests -q
python scripts/demo_finance.py
```

See [the finance contract](finance-contract.md) for inputs, results, and accounting
assumptions.

## Next backend section

The data loader, sample books, and finance tools are implemented and tested.
The report API, purchase checks, and upload UI are connected. Follow the
[live dashboard guide](live-dashboard.md) to start them and run browser tests.
Strands chat and narrative integration are also implemented. Offline checks use
fake agents. Live model validation needs an accessible provider/model and working
authentication. Configure `backend/.env` for local development or secure cloud
environment settings; do not commit credential values.

Cloud tasks already have isolated environments. Use the existing checkout; create
a Git worktree only when explicitly requested. Virtual environment files can be
retained in a cloud snapshot, but running servers must be restarted in each task.
