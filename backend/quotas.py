"""Usage metering: guest quotas and a per-caller rate limit.

Two separate mechanisms:

* ``GuestQuotaStore``  — lifetime counters per guest, per action. Backs the
  allowance in ``guest_policy``. Entries expire after ``ttl_seconds`` so a
  long-running process doesn't accumulate one entry per visitor forever; a guest
  who comes back after the TTL gets a fresh preview, which is the intended
  trade-off for not requiring an account.
* ``RateLimiter``      — a sliding window of recent requests per caller, applied
  to signed-in users as well, so one account can't saturate the worker.

Both are **in-process**. That is correct for the current single-instance
deployment and keeps the dependency list short. Running more than one worker or
replica means each holds its own counters, so the effective limit multiplies by
the replica count — move these to Redis before scaling out.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class GuestQuotaStore:
    """Lifetime per-guest, per-action counters with TTL eviction.

    ``clock`` defaults to ``time.monotonic`` and exists so tests can advance
    time deliberately instead of sleeping.
    """

    def __init__(self, ttl_seconds: int = 24 * 3600, clock=time.monotonic):
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        # guest_id -> {"used": {action: count}, "seen": clock timestamp}
        self._entries: dict[str, dict] = {}

    def _evict_expired(self, now: float) -> None:
        """Caller must hold the lock."""
        cutoff = now - self.ttl_seconds
        stale = [k for k, v in self._entries.items() if v["seen"] <= cutoff]
        for key in stale:
            del self._entries[key]

    def used(self, guest_id: str, action: str) -> int:
        """How many times this guest has performed ``action``."""
        now = self._clock()
        with self._lock:
            self._evict_expired(now)
            entry = self._entries.get(guest_id)
            return entry["used"].get(action, 0) if entry else 0

    def usage(self, guest_id: str) -> dict[str, int]:
        """All of this guest's counters, for the /guest/status endpoint."""
        now = self._clock()
        with self._lock:
            self._evict_expired(now)
            entry = self._entries.get(guest_id)
            return dict(entry["used"]) if entry else {}

    def try_consume(self, guest_id: str, action: str, limit: int) -> tuple[bool, int]:
        """Atomically take one unit of ``action`` if the guest has any left.

        Returns ``(allowed, used_after)``. When the quota is exhausted the
        counter is left untouched and ``allowed`` is False.
        """
        now = self._clock()
        with self._lock:
            self._evict_expired(now)
            entry = self._entries.setdefault(guest_id, {"used": {}, "seen": now})
            entry["seen"] = now
            current = entry["used"].get(action, 0)
            if current >= limit:
                return False, current
            entry["used"][action] = current + 1
            return True, current + 1

    def refund(self, guest_id: str, action: str) -> None:
        """Give back a consumed unit.

        Used when the request fails for a reason that isn't the guest's doing (a
        market-data outage, a solver error) — they shouldn't burn their single
        preview run on our own failure.
        """
        with self._lock:
            entry = self._entries.get(guest_id)
            if not entry:
                return
            current = entry["used"].get(action, 0)
            if current > 0:
                entry["used"][action] = current - 1

    def reset(self) -> None:
        """Drop every counter (tests)."""
        with self._lock:
            self._entries.clear()


class RateLimiter:
    """Sliding-window request limiter, keyed by caller id."""

    def __init__(self, max_requests: int, window_seconds: int,
                 clock=time.monotonic):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> tuple[bool, int]:
        """Record a request. Returns ``(allowed, retry_after_seconds)``.

        ``retry_after_seconds`` is 0 when allowed.
        """
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            # Drop callers whose whole window has aged out, so the dict doesn't
            # grow without bound.
            for key_ in [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]:
                if key_ != key:
                    del self._hits[key_]

            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                retry_after = int(hits[0] + self.window_seconds - now) + 1
                return False, max(retry_after, 1)
            hits.append(now)
            return True, 0

    def reset(self) -> None:
        """Drop every window (tests)."""
        with self._lock:
            self._hits.clear()
