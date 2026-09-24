"""Evaluation harness. A package, so `eval.run_eval` and `eval.advocate_eval` are one
module each whether they are imported by a test, by each other, or run as a script.

Importing this package also makes `app` importable. The engine lives under `backend/`,
which is not on the path when the eval is run from the repo root, and S8 asks for the
whole eval to be one command — so the package puts `backend/` on `sys.path` itself rather
than requiring every caller to remember `PYTHONPATH`. Inside the backend's own test suite
the entry is already there and this is a no-op.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"

for _path in (BACKEND, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
