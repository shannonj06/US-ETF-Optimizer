"""Runtime configuration for the API, read from the environment.

Everything that differs between local development and a deployed instance lives
here so no deployment detail is hard-coded in the route modules. Local runs pick
these up from the project's ``.env`` (loaded by ``configuration``); on Railway /
Render they come from the service's Variables tab.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# configuration.py (project root) calls load_dotenv(), so importing it populates
# os.environ from .env for local runs. The root is already on sys.path via core,
# but settings may be imported first (e.g. by tests), so make that explicit.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import configuration  # noqa: F401  (imported for its load_dotenv side effect)
except Exception:  # pragma: no cover - .env is optional in deployed envs
    pass


def _csv_env(name: str, default: str) -> list[str]:
    """Comma-separated env var -> list of trimmed, non-empty values."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        raw = default
    return [v.strip() for v in raw.split(",") if v.strip()]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# "development" | "production". Controls how much detail errors expose.
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# ── CORS ─────────────────────────────────────────────────────────────────────
# Comma-separated list. The default covers the two local dev servers plus the
# deployed client; override with ALLOWED_ORIGINS in production to lock it down.
_DEFAULT_ORIGINS = (
    "http://localhost:5173,"
    "http://localhost:3000,"
    "https://us-etf-optimizer.vercel.app"
)
ALLOWED_ORIGINS = _csv_env("ALLOWED_ORIGINS", _DEFAULT_ORIGINS)

# ── Supabase (used to verify the caller's access token) ──────────────────────
# SUPABASE_URL is the project URL, e.g. https://abcdefgh.supabase.co
# SUPABASE_ANON_KEY is the publishable key — the same one the client ships.
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_ANON_KEY = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_ANON_KEY)

# How long a successfully verified token is trusted without re-checking with
# Supabase. Keeps the hot path off the network without letting a revoked session
# linger for long.
TOKEN_CACHE_TTL_SECONDS = _int_env("TOKEN_CACHE_TTL_SECONDS", 300)

# Seconds to wait on the Supabase token-introspection call.
TOKEN_VERIFY_TIMEOUT_SECONDS = _int_env("TOKEN_VERIFY_TIMEOUT_SECONDS", 5)

# ── Access policy ────────────────────────────────────────────────────────────
# When true, unauthenticated callers may still use the API under the guest
# quotas in guest_policy.py. Set ALLOW_GUEST_ACCESS=false to require a login.
ALLOW_GUEST_ACCESS = _bool_env("ALLOW_GUEST_ACCESS", True)

# Rate limits (requests per window) for the expensive endpoints. Guests are held
# to their quota in guest_policy.py; these caps apply to signed-in users too.
RATE_LIMIT_WINDOW_SECONDS = _int_env("RATE_LIMIT_WINDOW_SECONDS", 3600)
RATE_LIMIT_MAX_REQUESTS = _int_env("RATE_LIMIT_MAX_REQUESTS", 30)

# Trust X-Forwarded-For when resolving the client IP. True behind a known proxy
# (Railway, Render, Fly); false when the API is exposed directly, since the
# header is client-controlled and would otherwise let guests reset their quota.
TRUST_PROXY_HEADERS = _bool_env("TRUST_PROXY_HEADERS", True)
