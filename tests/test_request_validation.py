"""Edge validation for /optimize and /evaluate.

Before these models existed both endpoints took bare dicts: a misspelled weight
key was silently ignored (the run used the default and the user never knew) and
an absurd number reached the solver as a failure hundreds of lines deep.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.optimize import EvaluateRequest, OptimizeRequest


class TestOptimizeRequest:
    def test_a_minimal_request_is_valid(self):
        request = OptimizeRequest(profile="conservative")
        assert request.market == "US"
        assert request.screening == {}

    def test_a_misspelled_score_weight_is_rejected_by_name(self):
        with pytest.raises(ValidationError) as caught:
            OptimizeRequest(profile="conservative", score_weights={"sharp": 0.3})
        assert "sharp" in str(caught.value)

    def test_a_misspelled_screening_key_is_rejected(self):
        with pytest.raises(ValidationError, match="aum_minimum"):
            OptimizeRequest(profile="conservative", screening={"aum_minimum": 1})

    def test_a_valid_partial_override_is_kept(self):
        request = OptimizeRequest(
            profile="enhanced", screening={"max_expense": 0.004}
        )
        assert request.screening == {"max_expense": 0.004}

    @pytest.mark.parametrize("screening", [
        {"max_expense": -0.1},     # negative cost
        {"max_expense": 2.0},      # 200% expense ratio
        {"max_duration": -1},      # negative duration
        {"max_duration": 500},     # 500-year duration
        {"aum_min": -5},           # negative AUM floor
    ])
    def test_out_of_range_screening_values_are_rejected(self, screening):
        with pytest.raises(ValidationError):
            OptimizeRequest(profile="conservative", screening=screening)

    @pytest.mark.parametrize("weights", [
        {"sharpe": -0.5},          # negative weight
        {"sharpe": 1.5},           # above 1
        {"sharpe": 0.0, "yield": 0.0},   # all zero: nothing to optimize for
    ])
    def test_invalid_optimizer_weights_are_rejected(self, weights):
        with pytest.raises(ValidationError):
            OptimizeRequest(profile="conservative", optimizer_weights=weights)

    def test_a_non_numeric_weight_is_rejected(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(profile="conservative", score_weights={"sharpe": "high"})

    def test_a_blank_profile_is_rejected(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(profile="   ")


class TestEvaluateRequest:
    def test_a_normal_portfolio_is_accepted_and_uppercased(self):
        request = EvaluateRequest(weights={"voo": 0.6, "bnd": 0.4})
        assert request.weights == {"VOO": 0.6, "BND": 0.4}

    def test_tickers_with_a_dot_or_hyphen_are_valid(self):
        request = EvaluateRequest(weights={"BRK-B": 0.5, "BAM.TO": 0.5})
        assert set(request.weights) == {"BRK-B", "BAM.TO"}

    def test_an_empty_portfolio_is_rejected(self):
        with pytest.raises(ValidationError, match="at least one"):
            EvaluateRequest(weights={})

    def test_all_zero_weights_are_rejected(self):
        with pytest.raises(ValidationError, match="sum to zero"):
            EvaluateRequest(weights={"VOO": 0.0, "BND": 0.0})

    def test_a_negative_weight_is_rejected(self):
        with pytest.raises(ValidationError, match="negative"):
            EvaluateRequest(weights={"VOO": -0.5, "BND": 1.5})

    @pytest.mark.parametrize("ticker", [
        "VOO; DROP TABLE",   # injection-shaped input
        "../../etc/passwd",  # path-shaped input
        "",                  # blank
        "TOOLONGTICKERNAME",
    ])
    def test_a_malformed_ticker_is_rejected(self, ticker):
        with pytest.raises(ValidationError):
            EvaluateRequest(weights={ticker: 1.0})

    def test_a_portfolio_larger_than_the_cap_is_rejected(self):
        oversized = {f"ET{i:02d}": 0.01 for i in range(60)}
        with pytest.raises(ValidationError, match="Too many holdings"):
            EvaluateRequest(weights=oversized)

    def test_an_unsupported_period_is_rejected(self):
        with pytest.raises(ValidationError):
            EvaluateRequest(weights={"VOO": 1.0}, period="20y")

    def test_an_absurd_risk_free_rate_is_rejected(self):
        with pytest.raises(ValidationError):
            EvaluateRequest(weights={"VOO": 1.0}, rf=50.0)
