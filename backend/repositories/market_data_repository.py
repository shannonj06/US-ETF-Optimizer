"""Price access for Cash Analysis.

Exposes a *panel* of unadjusted closing prices (one column per ticker) aligned
on a shared, tz-naive NYSE trading calendar, plus the two date primitives the
service needs:

  * ``common_execution_date`` — the earliest trading day on/after the requested
    start on which EVERY selected ticker has a real (non-filled) price. Using the
    common date prevents each holding from silently initializing on a different
    day when one ETF has a later inception.
  * ``last_common_valid_date`` — the latest trading day on/before the requested
    end on which every ticker has a real price (the analysis' ending date).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ._yf import get_history


@dataclass
class PricePanel:
    """A price matrix plus the metadata the service reports back to the user.

    ``prices``      : DataFrame indexed by tz-naive date, one column per ticker,
                      restricted to the common trading calendar (rows where every
                      ticker has a real price). No forward-filling — every value
                      is an actual observed close.
    ``first_dates`` : {ticker: first date it has any price} — used to explain a
                      pushed-forward execution date (inception).
    ``missing``     : tickers that returned no price data at all.
    """

    prices: pd.DataFrame
    first_dates: dict[str, pd.Timestamp]
    missing: list[str]


class MarketDataRepository:
    """Unadjusted-close price panels for a set of tickers over a window."""

    def get_price_panel(self, tickers: list[str], start, end) -> PricePanel:
        tickers = [t.strip().upper() for t in tickers]
        columns: dict[str, pd.Series] = {}
        first_dates: dict[str, pd.Timestamp] = {}
        missing: list[str] = []

        for ticker in tickers:
            hist = get_history(ticker, start, end)
            close = hist["Close"] if "Close" in hist.columns else pd.Series(dtype=float)
            close = close.dropna()
            close = close[close > 0]                       # a 0 close is a bad tick, not a price
            if close.empty:
                missing.append(ticker)
                continue
            columns[ticker] = close
            first_dates[ticker] = close.index.min()

        if not columns:
            return PricePanel(prices=pd.DataFrame(), first_dates={}, missing=missing)

        # Outer-join so we can see each ticker's own coverage, then keep only the
        # rows where ALL present tickers have a real price -> the common calendar.
        panel = pd.concat(columns, axis=1)
        panel = panel.dropna(how="any")
        return PricePanel(prices=panel, first_dates=first_dates, missing=missing)

    @staticmethod
    def common_execution_date(panel: PricePanel, requested_start) -> pd.Timestamp | None:
        """Earliest common trading day on/after ``requested_start`` (or None)."""
        if panel.prices.empty:
            return None
        req = pd.Timestamp(requested_start).normalize()
        eligible = panel.prices.index[panel.prices.index >= req]
        return eligible[0] if len(eligible) else None

    @staticmethod
    def last_common_valid_date(panel: PricePanel, requested_end) -> pd.Timestamp | None:
        """Latest common trading day on/before ``requested_end`` (or None)."""
        if panel.prices.empty:
            return None
        end = pd.Timestamp(requested_end).normalize()
        eligible = panel.prices.index[panel.prices.index <= end]
        return eligible[-1] if len(eligible) else None

    @staticmethod
    def latest_available_date(panel: PricePanel) -> pd.Timestamp | None:
        """Most recent common trading day in the panel (default analysis end)."""
        if panel.prices.empty:
            return None
        return panel.prices.index[-1]
