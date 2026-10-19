"""End-to-end access control over the HTTP surface.

The pipeline itself is stubbed - these tests are about who is allowed to call
what, how many times, and with which inputs. No network, no solver, no MongoDB.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import access
import auth
import core
import main_backend

GUEST_A = {"X-Forwarded-For": "203.0.113.10"}
GUEST_B = {"X-Forwarded-For": "203.0.113.11"}


@pytest.fixture
def client():
    return TestClient(main_backend.app)


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Replace the optimizer with a recorder, so a call is cheap and inspectable."""
    calls = []

    def fake_build(profile, screening, score_weights, optimizer_weights, market="US"):
        calls.append({
            "profile": profile,
            "screening": screening,
            "score_weights": score_weights,
            "optimizer_weights": optimizer_weights,
            "market": market,
        })
        return {"profile": profile, "market": market}

    monkeypatch.setattr(core, "build_portfolios", fake_build)
    monkeypatch.setattr(
        core, "serialize_optimize",
        lambda result, include_charts=True: {"methods": {}, "market": result["market"]},
    )
    return calls


@pytest.fixture
def stub_evaluate(monkeypatch):
    calls = []

    def fake_evaluate(weights, period, rf):
        calls.append({"weights": weights, "period": period, "rf": rf})
        return {"ok": True}

    monkeypatch.setattr(core, "evaluate_custom_weights", fake_evaluate)
    monkeypatch.setattr(core, "serialize_evaluate", lambda result: {"weights": []})
    return calls


@pytest.fixture
def signed_in(monkeypatch):
    """Make any bearer token resolve to a real user without calling Supabase."""
    monkeypatch.setattr(
        auth, "_verify_with_supabase",
        lambda token: {"id": f"user-{token}", "email": "someone@example.com"},
    )
    return {"Authorization": "Bearer test-token"}


# -- The removed file-backed portfolio routes --------------------------------
class TestDeadRoutesAreGone:
    """These shared one JSON file across every caller, with no authentication."""

    @pytest.mark.parametrize("method,path", [
        ("get", "/portfolios"),
        ("post", "/portfolios"),
        ("delete", "/portfolios/abc123"),
        ("get", "/portfolios/abc123/pdf"),
    ])
    def test_the_unauthenticated_portfolio_routes_no_longer_exist(
        self, client, method, path
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 404

    def test_no_route_mentions_portfolios_at_all(self):
        paths = [getattr(r, "path", "") for r in main_backend.app.routes]
        assert not [p for p in paths if "portfolio" in p.lower()]


# -- Health / catalogue ------------------------------------------------------
class TestHealth:
    def test_the_root_ping_stays_cheap(self, client):
        assert client.get("/").status_code == 200

    def test_health_reports_degraded_when_the_universe_is_unreachable(
        self, client, monkeypatch
    ):
        def unreachable(market="US"):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(core, "load_etf_data", unreachable)
        response = client.get("/health")
        assert response.status_code == 503, "the platform must be able to act on this"

    def test_health_is_ok_when_the_universe_loads(self, client, monkeypatch):
        monkeypatch.setattr(core, "load_etf_data", lambda market="US": [1, 2, 3])
        monkeypatch.setattr(access.settings, "SUPABASE_CONFIGURED", True)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_a_missing_auth_config_does_not_fail_readiness(self, client, monkeypatch):
        """It degrades the service; it does not stop it serving.

        Failing the probe here would make the platform restart a working
        instance in a loop because someone forgot one environment variable.
        """
        monkeypatch.setattr(core, "load_etf_data", lambda market="US": [1, 2, 3])
        monkeypatch.setattr(access.settings, "SUPABASE_CONFIGURED", False)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"
        assert response.json()["checks"]["auth"]["ok"] is False

    def test_losing_the_data_source_does_fail_readiness(self, client, monkeypatch):
        """No ETF universe means no endpoint can work - stop sending traffic."""
        def unreachable(market="US"):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(core, "load_etf_data", unreachable)
        monkeypatch.setattr(access.settings, "SUPABASE_CONFIGURED", True)
        assert client.get("/health").status_code == 503

    def test_health_never_echoes_the_underlying_error_text(self, client, monkeypatch):
        """A connection error can carry the MongoDB URI, password included."""
        secret = "mongodb+srv://admin:hunter2@cluster0.example.net"

        def unreachable(market="US"):
            raise RuntimeError(f"failed to connect to {secret}")

        monkeypatch.setattr(core, "load_etf_data", unreachable)
        assert secret not in client.get("/health").text


# -- Guest allowance ---------------------------------------------------------
class TestGuestQuota:
    def _optimize(self, client, headers, **overrides):
        body = {"profile": "conservative", "market": "US", **overrides}
        return client.post("/optimize", json=body, headers=headers)

    def test_a_guest_gets_one_optimization(self, client, stub_pipeline):
        assert self._optimize(client, GUEST_A).status_code == 200

    def test_the_second_optimization_is_refused(self, client, stub_pipeline):
        self._optimize(client, GUEST_A)
        response = self._optimize(client, GUEST_A)
        assert response.status_code == 402
        assert "account" in response.json()["detail"].lower()

    def test_the_refused_run_never_reaches_the_pipeline(self, client, stub_pipeline):
        self._optimize(client, GUEST_A)
        self._optimize(client, GUEST_A)
        assert len(stub_pipeline) == 1, "the expensive work must not run twice"

    def test_guests_are_metered_separately(self, client, stub_pipeline):
        self._optimize(client, GUEST_A)
        assert self._optimize(client, GUEST_B).status_code == 200

    def test_the_optimizer_and_the_evaluator_are_metered_separately(
        self, client, stub_pipeline, stub_evaluate
    ):
        """One developed portfolio plus one evaluated portfolio = the two allowed."""
        assert self._optimize(client, GUEST_A).status_code == 200
        evaluated = client.post(
            "/evaluate", json={"weights": {"VOO": 0.6, "BND": 0.4}}, headers=GUEST_A
        )
        assert evaluated.status_code == 200

    def test_a_third_portfolio_is_refused(
        self, client, stub_pipeline, stub_evaluate
    ):
        self._optimize(client, GUEST_A)
        client.post("/evaluate", json={"weights": {"VOO": 1.0}}, headers=GUEST_A)
        again = client.post("/evaluate", json={"weights": {"VOO": 1.0}}, headers=GUEST_A)
        assert again.status_code == 402

    def test_a_signed_in_user_is_not_metered(self, client, stub_pipeline, signed_in):
        for _ in range(4):
            response = self._optimize(client, {**GUEST_A, **signed_in})
            assert response.status_code == 200

    def test_a_pipeline_failure_refunds_the_guest(
        self, client, monkeypatch, stub_pipeline
    ):
        """A guest must not lose their single preview to our own outage."""
        def broken(*args, **kwargs):
            raise RuntimeError("yahoo finance is down")

        monkeypatch.setattr(core, "build_portfolios", broken)
        assert self._optimize(client, GUEST_A).status_code == 500

        monkeypatch.setattr(core, "build_portfolios",
                            lambda *a, **k: {"profile": "conservative", "market": "US"})
        assert self._optimize(client, GUEST_A).status_code == 200

    def test_the_response_tells_the_client_what_is_left(self, client, stub_pipeline):
        body = self._optimize(client, GUEST_A).json()
        assert body["access"]["remaining"]["optimize"] == 0
        assert body["access"]["remaining"]["cash_analysis"] == 1


class TestGuestStatusEndpoint:
    def test_a_fresh_guest_sees_the_full_allowance(self, client):
        body = client.get("/guest/status", headers=GUEST_A).json()
        assert body["is_guest"] is True
        assert body["remaining"] == {"optimize": 1, "evaluate": 1, "cash_analysis": 1}

    def test_checking_status_does_not_consume_anything(self, client, stub_pipeline):
        for _ in range(3):
            client.get("/guest/status", headers=GUEST_A)
        response = client.post(
            "/optimize", json={"profile": "conservative"}, headers=GUEST_A
        )
        assert response.status_code == 200

    def test_a_signed_in_user_is_reported_as_unlimited(self, client, signed_in):
        body = client.get("/guest/status", headers={**GUEST_A, **signed_in}).json()
        assert body["is_guest"] is False
        assert body["unlimited"] is True


# -- Guest input restrictions ------------------------------------------------
class TestGuestInputRestrictions:
    def test_a_guest_cannot_optimize_the_canadian_universe(self, client, stub_pipeline):
        response = client.post(
            "/optimize", json={"profile": "conservative", "market": "CA"},
            headers=GUEST_A,
        )
        assert response.status_code == 403
        assert not stub_pipeline

    def test_a_rejected_input_does_not_consume_the_quota(self, client, stub_pipeline):
        client.post("/optimize", json={"profile": "conservative", "market": "CA"},
                    headers=GUEST_A)
        allowed = client.post("/optimize", json={"profile": "conservative"},
                              headers=GUEST_A)
        assert allowed.status_code == 200

    def test_guest_tuning_is_discarded_in_favour_of_the_profile_defaults(
        self, client, stub_pipeline
    ):
        """A guest can pick a style; they cannot hand-tune the optimizer."""
        client.post("/optimize", json={
            "profile": "conservative",
            "screening": {"max_expense": 0.0001},
            "score_weights": {"yield": 1.0},
            "optimizer_weights": {"sharpe": 1.0},
        }, headers=GUEST_A)

        used = stub_pipeline[0]
        defaults = core.profile_defaults("conservative")
        assert used["screening"] == defaults["screening"]
        assert used["score_weights"] == defaults["score_weights"]
        assert used["optimizer_weights"] == defaults["optimizer_weights"]

    def test_the_response_marks_the_inputs_as_locked(self, client, stub_pipeline):
        body = client.post("/optimize", json={"profile": "conservative"},
                           headers=GUEST_A).json()
        assert body["inputs_locked"] is True

    def test_a_signed_in_user_keeps_their_overrides(
        self, client, stub_pipeline, signed_in
    ):
        client.post("/optimize", json={
            "profile": "conservative",
            "screening": {"max_expense": 0.0042},
        }, headers={**GUEST_A, **signed_in})
        assert stub_pipeline[0]["screening"]["max_expense"] == 0.0042

    def test_a_signed_in_user_gets_defaults_for_what_they_omit(
        self, client, stub_pipeline, signed_in
    ):
        client.post("/optimize", json={
            "profile": "conservative",
            "screening": {"max_expense": 0.0042},
        }, headers={**GUEST_A, **signed_in})
        defaults = core.profile_defaults("conservative")
        assert stub_pipeline[0]["screening"]["aum_min"] == defaults["screening"]["aum_min"]

    def test_a_guest_cannot_evaluate_an_oversized_portfolio(
        self, client, stub_evaluate
    ):
        oversized = {f"ET{i:02d}": 0.1 for i in range(10)}
        response = client.post("/evaluate", json={"weights": oversized}, headers=GUEST_A)
        assert response.status_code == 403
        assert not stub_evaluate

    def test_a_signed_in_user_may_evaluate_a_larger_portfolio(
        self, client, stub_evaluate, signed_in
    ):
        larger = {f"ET{i:02d}": 0.1 for i in range(10)}
        response = client.post(
            "/evaluate", json={"weights": larger}, headers={**GUEST_A, **signed_in}
        )
        assert response.status_code == 200


# -- Rate limiting -----------------------------------------------------------
class TestRateLimit:
    def test_a_signed_in_user_is_still_capped(
        self, client, stub_pipeline, signed_in, monkeypatch
    ):
        """One account must not be able to saturate the worker."""
        from quotas import RateLimiter
        monkeypatch.setattr(access, "rate_limiter", RateLimiter(2, 3600))

        headers = {**GUEST_A, **signed_in}
        assert client.post("/optimize", json={"profile": "conservative"},
                           headers=headers).status_code == 200
        assert client.post("/optimize", json={"profile": "conservative"},
                           headers=headers).status_code == 200
        limited = client.post("/optimize", json={"profile": "conservative"},
                              headers=headers)
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers


# -- Error handling ----------------------------------------------------------
class TestErrorResponses:
    def test_an_unknown_profile_is_a_404(self, client):
        response = client.post("/optimize", json={"profile": "nonexistent"},
                               headers=GUEST_A)
        assert response.status_code == 404

    def test_an_unknown_market_is_a_400(self, client, signed_in):
        response = client.post(
            "/optimize", json={"profile": "conservative", "market": "ZZ"},
            headers={**GUEST_A, **signed_in},
        )
        assert response.status_code == 400

    def test_an_invalid_payload_is_a_422(self, client):
        response = client.post(
            "/optimize",
            json={"profile": "conservative", "score_weights": {"nonsense": 0.5}},
            headers=GUEST_A,
        )
        assert response.status_code == 422

    def test_a_user_fixable_pipeline_error_is_a_422_not_a_500(
        self, client, monkeypatch, signed_in
    ):
        def nothing_survived(*args, **kwargs):
            raise ValueError("No ETFs survived screening. Loosen the filters.")

        monkeypatch.setattr(core, "build_portfolios", nothing_survived)
        response = client.post("/optimize", json={"profile": "conservative"},
                               headers={**GUEST_A, **signed_in})
        assert response.status_code == 422
        assert "survived screening" in response.json()["detail"]
