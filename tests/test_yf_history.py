"""The Yahoo Finance access layer's normalization and caching.

``repositories/_yf.py`` documents a specific price policy - unadjusted Close for
appreciation plus a separate Dividends column for income, so distributions are
never counted twice - but nothing verified that the fetch actually requests the
data that way. A future edit flipping ``auto_adjust`` to True would silently
inflate every return in the product. These tests make that a failing build.

yfinance is replaced with a stub, so nothing here touches the network.
"""

from __future__ import annotations

import pandas as pd
import pytest

from repositories import _yf


class StubTicker:
    """Stands in for ``yf.Ticker``; records how history() was called."""

    calls: list[dict] = []

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, **kwargs):
        StubTicker.calls.append({"symbol": self.symbol, **kwargs})
        return StubTicker.frame


@pytest.fixture
def stub_yf(monkeypatch):
    StubTicker.calls = []
    index = pd.DatetimeIndex(
        pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    ).tz_localize("America/New_York")
    StubTicker.frame = pd.DataFrame(
        {
            "Close": [100.0, 101.0, 102.0],
            "Dividends": [0.0, 0.5, 0.0],
            "Stock Splits": [0.0, 0.0, 0.0],
        },
        index=index,
    )
    monkeypatch.setattr(_yf.yf, "Ticker", StubTicker)
    _yf.clear_cache()
    yield StubTicker
    _yf.clear_cache()


class TestPricePolicy:
    def test_history_is_fetched_unadjusted(self, stub_yf):
        """auto_adjust=True would dividend-adjust Close and double-count income."""
        _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        assert stub_yf.calls[0]["auto_adjust"] is False

    def test_corporate_actions_are_requested(self, stub_yf):
        """Without actions=True there is no Dividends column to earn income from."""
        _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        assert stub_yf.calls[0]["actions"] is True

    def test_both_price_and_dividend_columns_survive(self, stub_yf):
        frame = _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        assert list(frame.columns) == ["Close", "Dividends", "Stock Splits"]

    def test_the_window_is_padded_so_the_endpoints_are_covered(self, stub_yf):
        """A start that lands on a holiday still needs the surrounding days."""
        _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        call = stub_yf.calls[0]
        assert pd.Timestamp(call["start"]) < pd.Timestamp("2024-01-02")
        assert pd.Timestamp(call["end"]) > pd.Timestamp("2024-01-04")


class TestNormalization:
    def test_the_index_is_returned_timezone_naive(self, stub_yf):
        """Dates are compared against plain calendar dates everywhere downstream."""
        frame = _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        assert frame.index.tz is None

    def test_timestamps_are_normalized_to_midnight(self, stub_yf):
        frame = _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        assert (frame.index == frame.index.normalize()).all()

    def test_a_missing_dividends_column_is_filled_with_zero(self, stub_yf, monkeypatch):
        """A ticker with no distributions must not break income accounting."""
        bare = StubTicker.frame[["Close"]].copy()
        monkeypatch.setattr(StubTicker, "frame", bare)
        frame = _yf.get_history("NODIV", "2024-01-02", "2024-01-04")
        assert "Dividends" in frame.columns
        assert (frame["Dividends"] == 0.0).all()

    def test_duplicate_dates_keep_the_last_observation(self, stub_yf, monkeypatch):
        doubled = pd.concat([StubTicker.frame, StubTicker.frame.tail(1)])
        monkeypatch.setattr(StubTicker, "frame", doubled)
        frame = _yf.get_history("DUP", "2024-01-02", "2024-01-04")
        assert not frame.index.duplicated().any()

    def test_the_index_comes_back_sorted(self, stub_yf, monkeypatch):
        shuffled = StubTicker.frame.iloc[[2, 0, 1]]
        monkeypatch.setattr(StubTicker, "frame", shuffled)
        frame = _yf.get_history("SHUF", "2024-01-02", "2024-01-04")
        assert frame.index.is_monotonic_increasing


class TestFailureHandling:
    def test_a_network_error_becomes_an_empty_frame(self, stub_yf, monkeypatch):
        """Callers turn an empty frame into an explicit warning, not a crash."""
        def explode(**kwargs):
            raise ConnectionError("yahoo is unreachable")

        monkeypatch.setattr(StubTicker, "history", lambda self, **kw: explode(**kw))
        frame = _yf.get_history("BOOM", "2024-01-02", "2024-01-04")
        assert frame.empty
        assert list(frame.columns) == ["Close", "Dividends", "Stock Splits"]

    def test_an_empty_response_becomes_an_empty_frame(self, stub_yf, monkeypatch):
        monkeypatch.setattr(StubTicker, "frame", pd.DataFrame())
        frame = _yf.get_history("EMPTY", "2024-01-02", "2024-01-04")
        assert frame.empty


class TestCaching:
    def test_repeated_reads_of_one_window_hit_yahoo_once(self, stub_yf):
        """Price and dividend repositories both read the same frame per ticker."""
        _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        assert len(stub_yf.calls) == 1

    def test_a_different_window_is_fetched_separately(self, stub_yf):
        _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        _yf.get_history("TEST", "2024-02-02", "2024-02-04")
        assert len(stub_yf.calls) == 2

    def test_the_ticker_is_normalized_before_caching(self, stub_yf):
        _yf.get_history("test", "2024-01-02", "2024-01-04")
        _yf.get_history("  TEST  ", "2024-01-02", "2024-01-04")
        assert len(stub_yf.calls) == 1, "casing/whitespace must not split the cache"

    def test_dates_in_different_forms_share_one_cache_entry(self, stub_yf):
        _yf.get_history("TEST", "2024-01-02", "2024-01-04")
        _yf.get_history("TEST", pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-04"))
        assert len(stub_yf.calls) == 1
