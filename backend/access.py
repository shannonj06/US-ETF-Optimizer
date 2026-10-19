"""The access gate every expensive endpoint goes through.

Ties together the three pieces the routes need:

  identity (auth.py) -> rate limit (quotas.py) -> guest allowance (guest_policy.py)

Routes call :func:`enforce` before doing any work, and — when the call turns out
to have failed through no fault of the caller — :func:`refund` so a guest doesn't
lose their single preview run to our own outage.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException

import guest_policy
import settings
from auth import Identity, resolve_identity
from quotas import GuestQuotaStore, RateLimiter
from utils.logger import logger

# Process-wide stores. See quotas.py on why in-process is the right scope today.
guest_quotas = GuestQuotaStore()
rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)


def enforce(identity: Identity, action: str) -> None:
    """Admit or reject this caller for ``action``.

    Raises ``HTTPException`` with the right status for the reason:
      401 guests disabled, 402 guest allowance used up, 429 rate limited.

    A guest's quota unit is consumed here, so the count reflects attempts that
    got as far as running. Refund it with :func:`refund` if the run then fails
    for an infrastructure reason.
    """
    allowed, retry_after = rate_limiter.check(identity.key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many requests. This endpoint runs a full optimization, so "
                f"it's rate limited — try again in about {retry_after} seconds."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    if not identity.is_guest:
        return

    if not settings.ALLOW_GUEST_ACCESS:
        raise HTTPException(
            status_code=401,
            detail="Sign in to use this feature.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    limit = guest_policy.quota_for(action)
    if limit is None:
        return

    ok, used = guest_quotas.try_consume(identity.guest_id, action, limit)
    if not ok:
        exc = guest_policy.GuestLimitExceeded(action, limit, used)
        logger.info("Guest %s hit the %s quota (%s/%s).",
                    identity.guest_id, action, used, limit)
        # 402 Payment Required: the request is well-formed and the caller is
        # recognized, but the free allowance is spent. Distinct from 429, which
        # the client should retry, and from 403, which would never succeed.
        raise HTTPException(
            status_code=402,
            detail=str(exc),
            headers={"X-Guest-Quota-Action": action,
                     "X-Guest-Quota-Limit": str(limit)},
        )


def refund(identity: Identity, action: str) -> None:
    """Return a guest's consumed quota unit after a server-side failure."""
    if identity.is_guest and guest_policy.quota_for(action) is not None:
        guest_quotas.refund(identity.guest_id, action)


def remaining(identity: Identity) -> dict:
    """What this caller has left, for the client to render its guest banner."""
    if not identity.is_guest:
        return {"is_guest": False, "unlimited": True}
    used = guest_quotas.usage(identity.guest_id)
    return {
        "is_guest": True,
        "unlimited": False,
        "policy": guest_policy.describe(),
        "used": {action: used.get(action, 0) for action in guest_policy.GUEST_QUOTAS},
        "remaining": {
            action: max(limit - used.get(action, 0), 0)
            for action, limit in guest_policy.GUEST_QUOTAS.items()
        },
    }


def guest_input_error(exc: guest_policy.GuestInputNotAllowed) -> HTTPException:
    """Map a restricted-input rejection to its HTTP form."""
    return HTTPException(status_code=403, detail=str(exc))


__all__ = [
    "guest_quotas", "rate_limiter", "enforce", "refund", "remaining",
    "guest_input_error", "resolve_identity", "Identity", "Depends",
]
