"""The metering primitives behind the guest allowance and the rate limit."""

from __future__ import annotations

import threading

from quotas import GuestQuotaStore, RateLimiter


class FakeClock:
    """A monotonic clock the test moves by hand, so nothing has to sleep."""

    def __init__(self, start: float = 1_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestGuestQuotaStore:
    def test_a_guest_can_consume_up_to_the_limit(self):
        store = GuestQuotaStore()
        assert store.try_consume("guest-a", "optimize", limit=1) == (True, 1)
        assert store.try_consume("guest-a", "optimize", limit=1) == (False, 1)

    def test_a_rejected_attempt_does_not_advance_the_counter(self):
        store = GuestQuotaStore()
        store.try_consume("guest-a", "optimize", limit=1)
        store.try_consume("guest-a", "optimize", limit=1)
        store.try_consume("guest-a", "optimize", limit=1)
        assert store.used("guest-a", "optimize") == 1

    def test_actions_are_metered_separately(self):
        store = GuestQuotaStore()
        store.try_consume("guest-a", "optimize", limit=1)
        allowed, _ = store.try_consume("guest-a", "evaluate", limit=1)
        assert allowed, "using the optimizer must not consume the evaluation"

    def test_guests_are_metered_independently(self):
        store = GuestQuotaStore()
        store.try_consume("guest-a", "optimize", limit=1)
        allowed, _ = store.try_consume("guest-b", "optimize", limit=1)
        assert allowed

    def test_a_refund_returns_the_consumed_unit(self):
        store = GuestQuotaStore()
        store.try_consume("guest-a", "optimize", limit=1)
        store.refund("guest-a", "optimize")
        assert store.used("guest-a", "optimize") == 0
        assert store.try_consume("guest-a", "optimize", limit=1)[0]

    def test_a_refund_never_drops_below_zero(self):
        store = GuestQuotaStore()
        store.refund("guest-a", "optimize")
        store.refund("guest-a", "optimize")
        assert store.used("guest-a", "optimize") == 0

    def test_a_counter_survives_inside_its_ttl(self):
        clock = FakeClock()
        store = GuestQuotaStore(ttl_seconds=3600, clock=clock)
        store.try_consume("guest-a", "optimize", limit=1)
        clock.advance(3599)
        assert store.used("guest-a", "optimize") == 1

    def test_entries_expire_so_the_store_cannot_grow_forever(self):
        clock = FakeClock()
        store = GuestQuotaStore(ttl_seconds=3600, clock=clock)
        store.try_consume("guest-a", "optimize", limit=1)
        clock.advance(3601)
        assert store.used("guest-a", "optimize") == 0

    def test_a_guest_returning_after_the_ttl_gets_a_fresh_preview(self):
        """The documented trade-off for not requiring an account."""
        clock = FakeClock()
        store = GuestQuotaStore(ttl_seconds=3600, clock=clock)
        store.try_consume("guest-a", "optimize", limit=1)
        clock.advance(7200)
        assert store.try_consume("guest-a", "optimize", limit=1)[0]

    def test_concurrent_consumers_cannot_exceed_the_limit(self):
        """The counter is shared mutable state; the lock has to hold under load."""
        store = GuestQuotaStore()
        granted: list[bool] = []
        lock = threading.Lock()

        def attempt():
            allowed, _ = store.try_consume("guest-a", "optimize", limit=5)
            with lock:
                granted.append(allowed)

        threads = [threading.Thread(target=attempt) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sum(granted) == 5, "exactly five of fifty attempts should win"


class TestRateLimiter:
    def test_requests_are_allowed_up_to_the_cap(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert [limiter.check("caller")[0] for _ in range(3)] == [True, True, True]

    def test_the_next_request_is_refused_with_a_retry_hint(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("caller")
        limiter.check("caller")
        allowed, retry_after = limiter.check("caller")
        assert not allowed
        assert 0 < retry_after <= 61

    def test_callers_have_separate_windows(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.check("caller-a")[0]
        assert limiter.check("caller-b")[0], "one caller must not limit another"

    def test_requests_stay_blocked_inside_the_window(self):
        clock = FakeClock()
        limiter = RateLimiter(max_requests=1, window_seconds=60, clock=clock)
        limiter.check("caller")
        clock.advance(59)
        assert not limiter.check("caller")[0]

    def test_a_window_that_has_elapsed_lets_requests_through(self):
        clock = FakeClock()
        limiter = RateLimiter(max_requests=1, window_seconds=60, clock=clock)
        limiter.check("caller")
        clock.advance(61)
        assert limiter.check("caller")[0]

    def test_the_window_slides_rather_than_resetting_in_blocks(self):
        """Two requests 40s apart with a 60s window: the cap still applies."""
        clock = FakeClock()
        limiter = RateLimiter(max_requests=2, window_seconds=60, clock=clock)
        limiter.check("caller")
        clock.advance(40)
        limiter.check("caller")
        clock.advance(10)                 # 50s after the first, 10s after the second
        assert not limiter.check("caller")[0]
        clock.advance(11)                 # the first has now aged out
        assert limiter.check("caller")[0]

    def test_concurrent_callers_cannot_exceed_the_cap(self):
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        granted: list[bool] = []
        lock = threading.Lock()

        def attempt():
            allowed, _ = limiter.check("caller")
            with lock:
                granted.append(allowed)

        threads = [threading.Thread(target=attempt) for _ in range(40)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sum(granted) == 10
