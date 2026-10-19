"""The guest allowance and its input restrictions.

These assert the *product decision* - one optimizer run, one evaluation, one
cash analysis, with defaults-only inputs - so a change to the limits has to be
deliberate rather than accidental.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import guest_policy


class TestQuotas:
    def test_a_guest_gets_one_of_each_metered_action(self):
        assert guest_policy.GUEST_QUOTAS == {
            "optimize": 1,
            "evaluate": 1,
            "cash_analysis": 1,
        }

    def test_two_portfolios_total(self):
        """One developed + one evaluated = the two portfolios a guest may make."""
        assert guest_policy.GUEST_MAX_PORTFOLIOS == 2

    def test_quota_for_unknown_action_is_unmetered(self):
        assert guest_policy.quota_for("something_else") is None

    def test_describe_exposes_every_limit_the_client_renders(self):
        described = guest_policy.describe()
        for key in ("quotas", "max_portfolios", "max_holdings",
                    "max_initial_cash", "max_history_years",
                    "locks_advanced_inputs", "allowed_markets"):
            assert key in described, f"describe() is missing '{key}'"

    def test_exceeding_a_quota_produces_an_actionable_message(self):
        exc = guest_policy.GuestLimitExceeded("optimize", limit=1, used=1)
        message = str(exc)
        assert "account" in message.lower(), "should point the guest at signing up"
        assert exc.action == "optimize"


class TestOptimizeRestrictions:
    def test_allows_a_standard_profile_on_the_us_universe(self):
        guest_policy.check_optimize("conservative", "US")   # does not raise

    def test_rejects_the_canadian_universe(self):
        with pytest.raises(guest_policy.GuestInputNotAllowed, match="US ETF universe"):
            guest_policy.check_optimize("conservative", "CA")

    def test_rejects_an_unknown_profile(self):
        with pytest.raises(guest_policy.GuestInputNotAllowed):
            guest_policy.check_optimize("bespoke", "US")

    def test_advanced_inputs_are_locked(self):
        """The route relies on this flag to substitute the profile defaults."""
        assert guest_policy.GUEST_LOCKS_ADVANCED_INPUTS is True


class TestEvaluateRestrictions:
    def _weights(self, n: int) -> dict:
        return {f"ETF{i}": 1 / n for i in range(n)}

    def test_allows_a_portfolio_at_the_holding_limit(self):
        guest_policy.check_evaluate(
            self._weights(guest_policy.GUEST_MAX_HOLDINGS), "5y", 0.04
        )

    def test_rejects_one_holding_over_the_limit(self):
        over = self._weights(guest_policy.GUEST_MAX_HOLDINGS + 1)
        with pytest.raises(guest_policy.GuestInputNotAllowed, match="up to"):
            guest_policy.check_evaluate(over, "5y", 0.04)

    def test_rejects_a_history_window_beyond_the_guest_range(self):
        with pytest.raises(guest_policy.GuestInputNotAllowed):
            guest_policy.check_evaluate(self._weights(2), "10y", 0.04)

    @pytest.mark.parametrize("rf", [-0.01, 0.5, 1.0])
    def test_rejects_an_out_of_range_risk_free_rate(self, rf):
        with pytest.raises(guest_policy.GuestInputNotAllowed, match="risk-free"):
            guest_policy.check_evaluate(self._weights(2), "5y", rf)


class TestCashAnalysisRestrictions:
    TODAY = date(2026, 9, 20)

    def test_allows_a_request_inside_every_limit(self):
        guest_policy.check_cash_analysis(
            holdings_count=3,
            initial_cash=10_000,
            start=date(2024, 1, 3),
            today=self.TODAY,
        )

    def test_rejects_too_many_holdings(self):
        with pytest.raises(guest_policy.GuestInputNotAllowed, match="up to"):
            guest_policy.check_cash_analysis(
                holdings_count=guest_policy.GUEST_MAX_HOLDINGS + 1,
                initial_cash=10_000,
                start=date(2024, 1, 3),
                today=self.TODAY,
            )

    def test_rejects_more_cash_than_the_preview_allows(self):
        with pytest.raises(guest_policy.GuestInputNotAllowed, match="initial cash"):
            guest_policy.check_cash_analysis(
                holdings_count=2,
                initial_cash=guest_policy.GUEST_MAX_INITIAL_CASH + 1,
                start=date(2024, 1, 3),
                today=self.TODAY,
            )

    def test_rejects_a_start_date_beyond_the_lookback_window(self):
        too_early = self.TODAY - timedelta(days=365 * 20)
        with pytest.raises(guest_policy.GuestInputNotAllowed, match="look back"):
            guest_policy.check_cash_analysis(
                holdings_count=2,
                initial_cash=10_000,
                start=too_early,
                today=self.TODAY,
            )

    def test_allows_a_start_date_just_inside_the_window(self):
        just_inside = self.TODAY - timedelta(
            days=365 * guest_policy.GUEST_MAX_HISTORY_YEARS - 1
        )
        guest_policy.check_cash_analysis(
            holdings_count=2,
            initial_cash=10_000,
            start=just_inside,
            today=self.TODAY,
        )
