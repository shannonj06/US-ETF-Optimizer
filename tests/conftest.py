"""Shared pytest setup.

Two things have to happen before any backend module is imported:

1. ``backend/`` goes on ``sys.path``. The app is run from that directory
   (``uvicorn main_backend:app``), so its modules import each other by bare name
   (``import core``, ``from schemas.optimize import ...``). Tests have to match.
2. The environment is pinned. ``backend/settings.py`` reads configuration at
   import time, so a developer's real ``.env`` would otherwise leak into the
   tests - in particular a real ``MONGODB_URL`` or Supabase project.

No test in this suite touches the network.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

for path in (ROOT, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Pinned before `import settings` happens anywhere downstream.
os.environ.update({
    "ENVIRONMENT": "test",
    "ALLOWED_ORIGINS": "http://localhost:5173",
    "ALLOW_GUEST_ACCESS": "true",
    "TRUST_PROXY_HEADERS": "true",
    "RATE_LIMIT_MAX_REQUESTS": "1000",
    "RATE_LIMIT_WINDOW_SECONDS": "3600",
})
# Make sure a developer's real credentials can't be picked up by a test run.
for leaked in ("MONGODB_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY"):
    os.environ.pop(leaked, None)


@pytest.fixture(autouse=True)
def _reset_access_state():
    """Give every test a clean rate limiter and guest ledger.

    Both stores are process-wide singletons, so without this the order tests run
    in would change their results.
    """
    import access
    import auth

    access.guest_quotas.reset()
    access.rate_limiter.reset()
    auth.clear_token_cache()
    yield
    access.guest_quotas.reset()
    access.rate_limiter.reset()
    auth.clear_token_cache()
