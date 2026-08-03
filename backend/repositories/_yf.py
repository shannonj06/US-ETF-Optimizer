"""Shared, cached low-level access to Yahoo Finance history.

Both repositories (price + dividend) read from the SAME normalized frame per
ticker, so a full Cash Analysis makes at most one external request per ticker.

Price policy for Cash Analysis
------------------------------
We fetch with ``auto_adjust=False`` and use the **unadjusted "Close"** for price
appreciation, and the separate **"Dividends"** column for income. yfinance's
"Close" is already *split*-adjusted (the series is continuous across splits) but
NOT *dividend*-adjusted, and its "Dividends" column is expressed on the same
split-adjusted per-share basis. That combination lets us:

  * hold a constant share count across splits (the price series is continuous), and
  * add dividends as separate cash

without ever double-counting distributions — which is exactly what would happen
if we used "Adj Close" (dividend-adjusted) for appreciation *and* added
dividends on top. See the module-level tests / handoff notes for the empirical
check on AAPL's 2020 4:1 split.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

import pandas as pd

try:  # reuse the project logger when importable; fall back to a no-op otherwise
    from utils.logger import logger
except Exception:  # pragma: no cover - logging is best-effort
    import logging

    logger = logging.getLogger("cash_analysis")

import yfinance as yf

# Timezone the whole feature normalizes to. Yahoo returns tz-aware US/Eastern
# timestamps; we strip the tz to calendar dates so string/date slicing is exact
# and every ticker aligns on the same NYSE trading calendar.
MARKET_TIMEZONE = "America/New_York"

# Fetches are padded a few days on each side so the requested window's own
# endpoints are covered even when they land on a weekend/holiday.
_FETCH_PAD_DAYS = 7

# (ticker, start_iso, end_iso) -> normalized history DataFrame. Process-local
# and unbounded, but the key space is tiny (a handful of tickers/windows per
# session) and each frame is small, so this is a deliberate simple cache.
_HISTORY_CACHE: dict[tuple[str, str, str], pd.DataFrame] = {}
_CACHE_LOCK = threading.Lock()

# Columns we keep from the raw yfinance frame.
_KEEP_COLUMNS = ["Close", "Dividends", "Stock Splits"]


def _to_iso(d) -> str:
    """Coerce a date/datetime/str/Timestamp into a plain ``YYYY-MM-DD`` string."""
    if isinstance(d, str):
        return pd.Timestamp(d).date().isoformat()
    if isinstance(d, pd.Timestamp):
        return d.date().isoformat()
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return pd.Timestamp(d).date().isoformat()


def _fetch_raw(ticker: str, start_iso: str, end_iso: str) -> pd.DataFrame:
    """One yfinance call, normalized to tz-naive calendar dates.

    Returns an empty frame (no rows) when the ticker has no data in the window,
    which callers translate into an explicit warning rather than a silent gap.
    """
    # Pad both ends and make `end` exclusive-safe by adding a day, so the last
    # requested trading day is always included.
    pad_start = (pd.Timestamp(start_iso) - timedelta(days=_FETCH_PAD_DAYS)).strftime("%Y-%m-%d")
    pad_end = (pd.Timestamp(end_iso) + timedelta(days=_FETCH_PAD_DAYS + 1)).strftime("%Y-%m-%d")

    try:
        raw = yf.Ticker(ticker).history(
            start=pad_start,
            end=pad_end,
            auto_adjust=False,   # keep unadjusted Close + a separate Dividends column
            actions=True,        # populate Dividends / Stock Splits
        )
    except Exception as exc:  # network / parsing failures -> empty, caller warns
        logger.warning("yfinance history failed for %s: %s", ticker, exc)
        return pd.DataFrame(columns=_KEEP_COLUMNS)

    if raw is None or raw.empty:
        return pd.DataFrame(columns=_KEEP_COLUMNS)

    cols = [c for c in _KEEP_COLUMNS if c in raw.columns]
    frame = raw[cols].copy()
    for missing in (c for c in _KEEP_COLUMNS if c not in frame.columns):
        frame[missing] = 0.0

    idx = frame.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(MARKET_TIMEZONE).tz_localize(None)
    frame.index = pd.DatetimeIndex(idx).normalize()
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame[_KEEP_COLUMNS]


def get_history(ticker: str, start, end) -> pd.DataFrame:
    """Cached, normalized history for one ticker over [start, end] (inclusive).

    The cache key includes the ticker and both endpoints (the required
    ticker/start/end/data-frequency/data-type cache-key contract; frequency and
    data-type are handled by the callers that slice columns off this frame).
    """
    ticker = ticker.strip().upper()
    key = (ticker, _to_iso(start), _to_iso(end))
    with _CACHE_LOCK:
        cached = _HISTORY_CACHE.get(key)
        if cached is not None:
            return cached
    frame = _fetch_raw(ticker, key[1], key[2])
    with _CACHE_LOCK:
        _HISTORY_CACHE[key] = frame
    return frame


def clear_cache() -> None:
    """Drop all cached history (used by tests)."""
    with _CACHE_LOCK:
        _HISTORY_CACHE.clear()
