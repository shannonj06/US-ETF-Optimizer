"""Dividend access for Cash Analysis.

Returns *actual* historical cash-distribution events per ticker (never an
estimate derived from an annual yield). Each event carries the ex-dividend date
and the per-share amount on the same split-adjusted basis as the price panel, so
``dividend_per_share × shares_held`` is internally consistent with the holdings'
constant share count.

Yahoo Finance only reliably exposes the **ex-dividend date** and the per-share
amount. Record date and payment date are not available from this source, so they
are returned as ``None`` and the event is marked ``date_type="ex_date"`` — the
service and UI surface that explicitly rather than pretending a payment date
exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ._yf import get_history


@dataclass
class DividendEvent:
    ticker: str
    ex_date: pd.Timestamp
    dividend_per_share: float
    # Not available from Yahoo; kept in the shape so a richer source can fill them
    # later without changing callers.
    record_date: pd.Timestamp | None = None
    pay_date: pd.Timestamp | None = None
    date_type: str = "ex_date"       # which date drives cash-flow bucketing


@dataclass
class DividendData:
    events: list[DividendEvent] = field(default_factory=list)
    # tickers that had a price history but no dividend rows in the window
    no_dividends: list[str] = field(default_factory=list)


class DividendRepository:
    """Actual per-share dividend events for a set of tickers over a window."""

    def get_dividends(self, tickers: list[str], start, end) -> DividendData:
        tickers = [t.strip().upper() for t in tickers]
        start_ts = pd.Timestamp(start).normalize()
        end_ts = pd.Timestamp(end).normalize()

        events: list[DividendEvent] = []
        no_dividends: list[str] = []

        for ticker in tickers:
            hist = get_history(ticker, start, end)
            if "Dividends" not in hist.columns or hist.empty:
                no_dividends.append(ticker)
                continue

            divs = hist["Dividends"]
            divs = divs[(divs > 0) & (divs.index >= start_ts) & (divs.index <= end_ts)]
            if divs.empty:
                no_dividends.append(ticker)
                continue

            for ex_date, amount in divs.items():
                events.append(
                    DividendEvent(
                        ticker=ticker,
                        ex_date=pd.Timestamp(ex_date).normalize(),
                        dividend_per_share=float(amount),
                    )
                )

        events.sort(key=lambda e: (e.ex_date, e.ticker))
        return DividendData(events=events, no_dividends=no_dividends)
