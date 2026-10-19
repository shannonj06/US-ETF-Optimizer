"""Golden-value tests for the Cash Analysis money math.

This is the code where a silent error is most expensive: it produces
plausible-looking dollar figures that a person might act on. Every expected
number below is computed by hand in the test name or comment, not read back
from the implementation.

The repositories are replaced with fakes built on synthetic price frames, so
these tests are deterministic and never touch the network. The date-resolution
logic is NOT faked - the fakes subclass the real repositories and override only
the fetch, so ``common_execution_date`` and friends run for real.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from repositories.dividend_repository import DividendData, DividendEvent, DividendRepository
from repositories.market_data_repository import MarketDataRepository, PricePanel
from schemas.cash_analysis import CashAnalysisRequest
from services.cash_analysis_service import CashAnalysisError, CashAnalysisService, _money, _round


# -- Fakes -------------------------------------------------------------------
class FakeMarketRepo(MarketDataRepository):
    """Serves a caller-supplied price frame; real date logic runs on top."""

    def __init__(self, prices: pd.DataFrame, missing: list[str] | None = None):
        self._prices = prices
        self._missing = missing or []

    def get_price_panel(self, tickers, start, end) -> PricePanel:
        if self._prices.empty:
            return PricePanel(pd.DataFrame(), {}, self._missing)
        frame = self._prices.loc[
            (self._prices.index >= pd.Timestamp(start))
            & (self._prices.index <= pd.Timestamp(end))
        ]
        return PricePanel(
            prices=frame,
            first_dates={t: frame.index.min() for t in frame.columns},
            missing=self._missing,
        )


class FakeDividendRepo(DividendRepository):
    def __init__(self, events: list[DividendEvent] | None = None,
                 no_dividends: list[str] | None = None):
        self._events = events or []
        self._no_dividends = no_dividends or []

    def get_dividends(self, tickers, start, end) -> DividendData:
        return DividendData(events=list(self._events),
                            no_dividends=list(self._no_dividends))


def price_frame(series: dict[str, tuple[float, float]],
                start="2024-01-02", end="2024-06-28") -> pd.DataFrame:
    """A business-day frame that moves linearly from an open to a close price.

    ``series`` maps ticker -> (first price, last price). Linear is fine: every
    assertion here is about the first and last row.
    """
    index = pd.bdate_range(start, end)
    data = {}
    for ticker, (first, last) in series.items():
        step = (last - first) / (len(index) - 1)
        data[ticker] = [round(first + step * i, 6) for i in range(len(index))]
    frame = pd.DataFrame(data, index=index)
    # Pin the endpoints exactly - float accumulation must not move them.
    for ticker, (first, last) in series.items():
        frame.iloc[0, frame.columns.get_loc(ticker)] = first
        frame.iloc[-1, frame.columns.get_loc(ticker)] = last
    return frame


def build_request(portfolio, cash=10_000.0, start="2024-01-02",
                  end="2024-06-28", **kwargs) -> CashAnalysisRequest:
    return CashAnalysisRequest(
        portfolio=portfolio,
        initial_cash=cash,
        requested_start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
        **kwargs,
    )


def run(prices, portfolio, events=None, **kwargs) -> dict:
    service = CashAnalysisService(
        market_repo=FakeMarketRepo(prices),
        dividend_repo=FakeDividendRepo(events),
    )
    return service.run(build_request(portfolio, **kwargs))


# -- Single holding, every figure hand-computed ------------------------------
class TestSingleHolding:
    """$10,000 into TEST at $100.00, ending at $110.00, one $1.00 dividend.

    shares          = 10000 / 100      = 100
    ending value    = 100 * 110        = 11,000
    dividend cash   = 100 * 1.00       = 100
    total value     = 11,000 + 100     = 11,100
    paper gain      = 11,000 - 10,000  = 1,000   (10.00%)
    total gain      = 11,100 - 10,000  = 1,100   (11.00%)
    """

    @pytest.fixture
    def result(self):
        prices = price_frame({"TEST": (100.0, 110.0)})
        events = [DividendEvent(
            ticker="TEST",
            ex_date=pd.Timestamp("2024-03-15"),
            dividend_per_share=1.00,
        )]
        return run(prices, [{"ticker": "TEST", "weight": 1.0}], events)

    def test_share_count(self, result):
        assert result["holdings"][0]["shares"] == 100.0

    def test_cost_basis_is_the_whole_allocation(self, result):
        assert result["summary"]["cost_basis"] == 10_000.00

    def test_ending_holdings_value(self, result):
        assert result["summary"]["current_holdings_value"] == 11_000.00

    def test_dividend_income(self, result):
        assert result["summary"]["total_dividend_income"] == 100.00

    def test_total_portfolio_value(self, result):
        assert result["summary"]["total_portfolio_value"] == 11_100.00

    def test_paper_gain_excludes_dividends(self, result):
        assert result["summary"]["paper_gain_loss"] == 1_000.00
        assert result["summary"]["paper_return_pct"] == 10.0

    def test_total_gain_includes_dividends(self, result):
        assert result["summary"]["total_gain_loss"] == 1_100.00
        assert result["summary"]["total_return_pct"] == 11.0

    def test_price_and_income_returns_are_reported_separately(self, result):
        summary = result["summary"]
        assert summary["price_return"] == 1_000.00
        assert summary["income_return"] == 100.00
        assert summary["total_return"] == 1_100.00

    def test_the_two_components_sum_to_the_total(self, result):
        """The double-counting guard: income and price never overlap."""
        summary = result["summary"]
        assert summary["price_return"] + summary["income_return"] == pytest.approx(
            summary["total_gain_loss"]
        )


# -- Multiple holdings -------------------------------------------------------
class TestTwoHoldings:
    """60/40 of $10,000: A $6,000 at $50 -> $60, B $4,000 at $20 -> $25.

    A: 120 shares -> 7,200     B: 200 shares -> 5,000
    total = 12,200, gain = 2,200 (22.00%)
    """

    @pytest.fixture
    def result(self):
        prices = price_frame({"AAA": (50.0, 60.0), "BBB": (20.0, 25.0)})
        return run(prices, [
            {"ticker": "AAA", "weight": 0.6},
            {"ticker": "BBB", "weight": 0.4},
        ])

    def test_each_holding_gets_its_share_count(self, result):
        by_ticker = {h["ticker"]: h for h in result["holdings"]}
        assert by_ticker["AAA"]["shares"] == 120.0
        assert by_ticker["BBB"]["shares"] == 200.0

    def test_total_value(self, result):
        assert result["summary"]["total_portfolio_value"] == 12_200.00

    def test_total_return(self, result):
        assert result["summary"]["total_return_pct"] == 22.0

    def test_weight_drift_is_reported(self, result):
        """AAA grew faster, so it ends above its 60% target."""
        by_ticker = {h["ticker"]: h for h in result["holdings"]}
        # 7,200 / 12,200 = 59.0164%  ->  drift from 60% is negative
        assert by_ticker["AAA"]["current_weight"] == pytest.approx(59.0164, abs=1e-3)
        assert by_ticker["AAA"]["weight_drift"] < 0

    def test_percent_weights_are_accepted_as_well_as_fractions(self):
        prices = price_frame({"AAA": (50.0, 60.0), "BBB": (20.0, 25.0)})
        result = run(prices, [
            {"ticker": "AAA", "weight": 60},
            {"ticker": "BBB", "weight": 40},
        ])
        assert result["summary"]["total_portfolio_value"] == 12_200.00


# -- Dividend entitlement ----------------------------------------------------
class TestDividendEntitlement:
    """You must hold the shares *before* the ex-date to be paid."""

    def _run_with_ex_date(self, ex_date: str):
        prices = price_frame({"TEST": (100.0, 100.0)})
        events = [DividendEvent(
            ticker="TEST",
            ex_date=pd.Timestamp(ex_date),
            dividend_per_share=2.00,
        )]
        return run(prices, [{"ticker": "TEST", "weight": 1.0}], events)

    def test_a_dividend_on_the_execution_date_is_not_credited(self):
        """Buying on the ex-date means you do not receive that distribution."""
        result = self._run_with_ex_date("2024-01-02")
        assert result["summary"]["total_dividend_income"] == 0.00

    def test_a_dividend_the_day_after_execution_is_credited(self):
        result = self._run_with_ex_date("2024-01-03")
        assert result["summary"]["total_dividend_income"] == 200.00

    def test_a_dividend_after_the_ending_date_is_not_credited(self):
        result = self._run_with_ex_date("2024-08-15")
        assert result["summary"]["total_dividend_income"] == 0.00

    def test_a_dividend_on_the_ending_date_is_credited(self):
        result = self._run_with_ex_date("2024-06-28")
        assert result["summary"]["total_dividend_income"] == 200.00

    def test_several_distributions_accumulate(self):
        prices = price_frame({"TEST": (100.0, 100.0)})
        events = [
            DividendEvent("TEST", pd.Timestamp("2024-03-15"), 0.50),
            DividendEvent("TEST", pd.Timestamp("2024-06-14"), 0.75),
        ]
        result = run(prices, [{"ticker": "TEST", "weight": 1.0}], events)
        # 100 shares * (0.50 + 0.75)
        assert result["summary"]["total_dividend_income"] == 125.00


# -- Whole shares ------------------------------------------------------------
class TestWholeShares:
    """$10,000 at $300.00 with fractional shares off: 33 shares, $100 left."""

    @pytest.fixture
    def result(self):
        prices = price_frame({"TEST": (300.0, 300.0)})
        return run(prices, [{"ticker": "TEST", "weight": 1.0}],
                   allow_fractional_shares=False)

    def test_shares_are_floored_not_rounded(self, result):
        assert result["holdings"][0]["shares"] == 33.0

    def test_the_unspent_cash_is_kept_as_residual(self, result):
        assert result["summary"]["residual_cash"] == 100.00

    def test_residual_cash_is_counted_in_the_total(self, result):
        # 33 * 300 = 9,900 of stock + 100 cash = the original 10,000
        assert result["summary"]["total_portfolio_value"] == 10_000.00
        assert result["summary"]["total_gain_loss"] == 0.00

    def test_a_holding_too_small_for_one_share_warns(self):
        prices = price_frame({"TEST": (300.0, 300.0)})
        result = run(prices, [{"ticker": "TEST", "weight": 1.0}],
                     cash=100.0, allow_fractional_shares=False)
        codes = [w["code"] for w in result["warnings"]]
        assert "insufficient_cash_for_share" in codes
        assert result["holdings"][0]["shares"] == 0.0


# -- Weight normalization ----------------------------------------------------
class TestWeightNormalization:
    def test_weights_that_do_not_sum_to_one_are_normalized(self):
        """0.5 / 0.3 -> 62.5% / 37.5% of the cash."""
        prices = price_frame({"AAA": (100.0, 100.0), "BBB": (100.0, 100.0)})
        result = run(prices, [
            {"ticker": "AAA", "weight": 0.5},
            {"ticker": "BBB", "weight": 0.3},
        ])
        by_ticker = {h["ticker"]: h for h in result["holdings"]}
        assert by_ticker["AAA"]["allocated_cash"] == 6_250.00
        assert by_ticker["BBB"]["allocated_cash"] == 3_750.00

    def test_a_materially_different_sum_produces_a_warning(self):
        prices = price_frame({"AAA": (100.0, 100.0), "BBB": (100.0, 100.0)})
        result = run(prices, [
            {"ticker": "AAA", "weight": 0.5},
            {"ticker": "BBB", "weight": 0.2},
        ])
        assert result["warnings"], "a 30% shortfall should be surfaced"
        assert result["metadata"]["normalization_applied"] is True

    def test_all_the_cash_is_always_allocated(self):
        prices = price_frame({"AAA": (100.0, 100.0), "BBB": (100.0, 100.0)})
        result = run(prices, [
            {"ticker": "AAA", "weight": 0.5},
            {"ticker": "BBB", "weight": 0.3},
        ])
        allocated = sum(h["allocated_cash"] for h in result["holdings"])
        assert allocated == pytest.approx(10_000.00)


# -- Error cases -------------------------------------------------------------
class TestUserFixableErrors:
    def test_an_unknown_ticker_is_reported_by_name(self):
        service = CashAnalysisService(
            market_repo=FakeMarketRepo(pd.DataFrame(), missing=["NOTREAL"]),
            dividend_repo=FakeDividendRepo(),
        )
        request = build_request([{"ticker": "NOTREAL", "weight": 1.0}])
        with pytest.raises(CashAnalysisError, match="NOTREAL"):
            service.run(request)

    def test_no_overlapping_history_is_reported(self):
        service = CashAnalysisService(
            market_repo=FakeMarketRepo(pd.DataFrame()),
            dividend_repo=FakeDividendRepo(),
        )
        request = build_request([{"ticker": "TEST", "weight": 1.0}])
        with pytest.raises(CashAnalysisError):
            service.run(request)

    def test_no_common_trading_day_after_the_start_is_reported(self):
        """Every price predates the requested start."""
        prices = price_frame({"TEST": (100.0, 100.0)},
                             start="2024-01-02", end="2024-02-01")
        service = CashAnalysisService(
            market_repo=FakeMarketRepo(prices),
            dividend_repo=FakeDividendRepo(),
        )
        request = build_request(
            [{"ticker": "TEST", "weight": 1.0}],
            start="2024-03-01", end="2024-06-28",
        )
        with pytest.raises(CashAnalysisError):
            service.run(request)


# -- Execution-date resolution -----------------------------------------------
class TestExecutionDate:
    def test_a_weekend_start_rolls_forward_to_the_next_trading_day(self):
        prices = price_frame({"TEST": (100.0, 110.0)})
        # 2024-03-02 is a Saturday; the next business day is Monday the 4th.
        result = run(prices, [{"ticker": "TEST", "weight": 1.0}],
                     start="2024-03-02", end="2024-06-28")
        assert result["execution"]["actual_execution_date"] == "2024-03-04"
        assert result["execution"]["date_adjusted"] is True

    def test_a_trading_day_start_is_used_as_is(self):
        prices = price_frame({"TEST": (100.0, 110.0)})
        result = run(prices, [{"ticker": "TEST", "weight": 1.0}])
        assert result["execution"]["actual_execution_date"] == "2024-01-02"
        assert result["execution"]["date_adjusted"] is False

    def test_the_price_field_is_the_unadjusted_close(self):
        """Documented invariant: appreciation must not use a dividend-adjusted series."""
        prices = price_frame({"TEST": (100.0, 110.0)})
        result = run(prices, [{"ticker": "TEST", "weight": 1.0}])
        assert result["metadata"]["price_field"] == "unadjusted_close"


# -- Money rounding ----------------------------------------------------------
class TestMoneyRounding:
    """Cash is rounded half-up, not with Python's default banker's rounding.

    ``round(0.125, 2)`` is 0.12 in Python; a dollar figure shown to a person
    should be 0.13. These pin that choice.
    """

    @pytest.mark.parametrize("value,expected", [
        ("0.125", 0.13),
        ("0.135", 0.14),
        ("2.345", 2.35),
        ("-0.125", -0.13),
        ("1234.565", 1234.57),
    ])
    def test_money_rounds_half_away_from_zero(self, value, expected):
        assert _money(Decimal(value)) == expected

    def test_money_keeps_exact_cents_untouched(self):
        assert _money(Decimal("11100.00")) == 11_100.00

    def test_round_helper_respects_the_requested_places(self):
        assert _round(Decimal("1.23456789"), 4) == 1.2346
