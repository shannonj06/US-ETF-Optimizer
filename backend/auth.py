"""Caller identity: a signed-in Supabase user, or a metered guest.

The React client authenticates against Supabase and holds an access token. It
sends that token as ``Authorization: Bearer <token>``; this module turns it into
an ``Identity`` the routes can act on.

Why introspection instead of local signature checks
---------------------------------------------------
Supabase projects sign tokens with either a shared HS256 secret or an asymmetric
key served from JWKS, and which one is in use depends on when the project was
created. Asking Supabase's ``/auth/v1/user`` endpoint works for both, needs no
extra secret in the deployment, and immediately reflects a revoked session. The
cost is one network call per token, which ``_TOKEN_CACHE`` amortizes over
``TOKEN_CACHE_TTL_SECONDS``.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass

import requests
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import settings
from utils.logger import logger

# auto_error=False: a missing header is a guest, not an error. The routes decide
# whether guests are acceptable.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    """Who is calling.

    is_guest : True when no valid Supabase session was presented.
    user_id  : the Supabase user UUID, or None for guests.
    guest_id : stable opaque id for a guest (derived from the client IP), used
               to meter the guest allowance. None for signed-in users.
    key      : the rate-limit bucket for this caller.
    """

    is_guest: bool
    user_id: str | None
    email: str | None
    guest_id: str | None
    key: str

    @property
    def label(self) -> str:
        """Short description for log lines (never the raw email or token)."""
        return f"guest:{self.guest_id}" if self.is_guest else f"user:{self.user_id}"


# token -> (expires_at_monotonic, user payload)
_TOKEN_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()


def _cache_get(token: str) -> dict | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _TOKEN_CACHE.get(token)
        if hit is None:
            return None
        expires_at, payload = hit
        if expires_at < now:
            del _TOKEN_CACHE[token]
            return None
        return payload


def _cache_put(token: str, payload: dict) -> None:
    now = time.monotonic()
    with _CACHE_LOCK:
        # Opportunistically drop anything already expired so the cache stays
        # proportional to the number of *active* sessions.
        for key in [k for k, (exp, _) in _TOKEN_CACHE.items() if exp < now]:
            del _TOKEN_CACHE[key]
        _TOKEN_CACHE[token] = (now + settings.TOKEN_CACHE_TTL_SECONDS, payload)


def clear_token_cache() -> None:
    """Drop every cached token (tests, and after a config change)."""
    with _CACHE_LOCK:
        _TOKEN_CACHE.clear()


def _verify_with_supabase(token: str) -> dict | None:
    """Exchange an access token for its user payload, or None if invalid."""
    if not settings.SUPABASE_CONFIGURED:
        return None
    try:
        response = requests.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.SUPABASE_ANON_KEY,
            },
            timeout=settings.TOKEN_VERIFY_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # Auth provider unreachable. Fail closed (the caller is treated as a
        # guest) rather than trusting an unverified token.
        logger.warning("Supabase token verification failed to connect: %s", exc)
        return None

    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except ValueError:
        logger.warning("Supabase returned a non-JSON user payload.")
        return None
    return payload if payload.get("id") else None


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    ``X-Forwarded-For`` is client-controlled, so it is only consulted when the
    deployment says it sits behind a proxy that rewrites it
    (``TRUST_PROXY_HEADERS``). Otherwise a guest could reset their quota by
    spoofing the header.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Left-most entry is the original client; the proxy appends its own.
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _guest_id(request: Request) -> str:
    """Stable, non-reversible id for an unauthenticated caller.

    Hashed so raw IP addresses aren't held in memory or written to logs.
    """
    return hashlib.sha256(client_ip(request).encode("utf-8")).hexdigest()[:16]


def resolve_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Identity:
    """FastAPI dependency: the caller's identity. Never raises for guests."""
    token = credentials.credentials.strip() if credentials else ""
    if token:
        payload = _cache_get(token)
        if payload is None:
            payload = _verify_with_supabase(token)
            if payload is not None:
                _cache_put(token, payload)
        if payload is not None:
            user_id = str(payload["id"])
            return Identity(
                is_guest=False,
                user_id=user_id,
                email=payload.get("email"),
                guest_id=None,
                key=f"user:{user_id}",
            )
        # A token was sent but didn't verify (expired, revoked, wrong project).
        # Falling through to guest keeps the preview working instead of hard-
        # failing a stale tab, and the guest quota still applies.
        logger.info("Rejected an unverifiable access token; treating as guest.")

    gid = _guest_id(request)
    return Identity(
        is_guest=True, user_id=None, email=None, guest_id=gid, key=f"guest:{gid}"
    )


def require_user(identity: Identity = Depends(resolve_identity)) -> Identity:
    """Dependency for routes that a guest may not call at all."""
    if identity.is_guest:
        raise HTTPException(
            status_code=401,
            detail="Sign in to use this feature.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity
