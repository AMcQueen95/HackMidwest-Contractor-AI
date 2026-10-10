#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use Python 3.12 for this validated bootstrap"'
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

pip_cache="${PIP_CACHE_DIR:-$repo_root/.venv/pip-cache}"
.venv/bin/python -m pip --cache-dir "$pip_cache" install -r requirements/backend-bootstrap.txt
.venv/bin/python -m pip --cache-dir "$pip_cache" check
.venv/bin/python scripts/validate_backend_stack.py
