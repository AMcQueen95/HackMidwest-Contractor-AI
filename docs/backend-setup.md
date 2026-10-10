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
The remaining sections are Strands agents and the API/UI, including an actual
server startup command.
Model integration will also need a verified provider, region, model ID, and
working authentication. Add credential values securely through environment
settings; do not commit them.

Cloud tasks already have isolated environments. Use the existing checkout; create
a Git worktree only when explicitly requested. Virtual environment files can be
retained in a cloud snapshot, but running servers must be restarted in each task.
