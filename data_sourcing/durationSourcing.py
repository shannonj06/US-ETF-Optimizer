"""
duration_source.py
------------------
Get an ETF's effective duration (in years) from a ticker, for free.

Strategy (layered, best source first):

    get_duration(ticker, name=None)
      1. Yahoo Finance via yfinance  -> real reported effective duration
      2. Estimate from the fund NAME -> maturity band + asset class -> duration
      3. Estimate from the STYLE bucket (your classifier) -> representative value
    ... always returns a value + the source + a confidence flag, and caches.

Why this design:
  * Effective duration is a paid field in most bulk datasets, but Yahoo exposes
    it per-ticker for free in the `topHoldings` module (yfinance surfaces it as
    `Ticker(t).funds_data.bond_holdings`). That covers the large majority of US
    bond ETFs.
  * For the funds Yahoo is missing/blank, the NAME usually states the maturity
    band ("1-3 Year", "20+ Year", "0-5 Year"), and duration is a well-behaved
    function of maturity. We approximate it with a par-coupon-bond formula that
    is calibrated to published fund durations (see _macaulay_par below).
  * The style bucket is the last-resort floor so you never get a blank.

NOTE: the Yahoo layer needs outbound internet (query1.finance.yahoo.com). Run it
on your own machine; it is intentionally wrapped in try/except so the module
still works (via estimation) where the network is unavailable.
"""

import json
import os
import re

try:
    from style_mapping import classify_etf_name   # your existing module
except Exception:                                   # keep usable standalone
    classify_etf_name = None


# ===========================================================================
# Layer 1 -- Yahoo Finance (free, real reported duration)
# ===========================================================================
def get_duration_yahoo(ticker):
    """Return reported effective duration in years, or None.

    Uses yfinance FundsData -> bond_holdings, whose index is
    ['Duration','Maturity','Credit Quality'] with the ticker as a column.
    """
    try:
        import yfinance as yf
        bh = yf.Ticker(ticker).funds_data.bond_holdings
        val = bh.loc["Duration", ticker]
        val = float(val)
        if val == val and val > 0:        # not NaN, positive
            return round(val, 2)
    except Exception:
        pass
    return None


# ===========================================================================
# Layer 2 -- estimate from the fund name (maturity band -> duration)
# ===========================================================================
# Representative yield-to-maturity per asset class, used only to turn an
# average maturity into a duration via the par-bond formula. These are
# coarse but calibrated so the output matches published fund durations
# (e.g. 25y Treasury -> ~16y, 8.5y -> ~7.4y, 2y -> ~1.9y).
_YIELD_BY_CLASS = {
    "treasury": 0.040, "government": 0.040, "agg": 0.040, "ig": 0.045,
    "muni": 0.035, "tips": 0.030, "hy": 0.070, "em": 0.060, "generic": 0.045,
}


def _macaulay_par(m, y):
    """Macaulay duration (years) of a par coupon bond, maturity m, yield y."""
    if m <= 0:
        return 0.0
    return (1 + y) / y * (1 - (1 + y) ** (-m))


def _maturity_band(s):
    """Return (low, high) average-maturity bounds in years from the name."""
    # months
    m = re.findall(r'(\d+)\s*-\s*(\d+)\s*month', s)
    if m:
        a, b = m[-1]
        return int(a) / 12.0, int(b) / 12.0
    m = re.findall(r'(\d+)\s*month', s)
    if m:
        v = int(m[-1]) / 12.0
        return 0.0, v
    if "six month" in s or "6 month" in s:
        return 0.25, 0.5
    if "three month" in s or "3 month" in s:
        return 0.0, 0.25
    # "N+ year"  -> open ended, assume roughly N..N+8
    m = re.findall(r'(\d+)\s*\+\s*year', s)
    if m:
        n = max(int(x) for x in m)
        return float(n), float(n + 8)
    # "A-B year"
    m = re.findall(r'(\d+)\s*-\s*(\d+)\s*year', s)
    if m:
        a, b = max(m, key=lambda t: int(t[1]))
        return float(a), float(b)
    # single "N year"
    m = re.findall(r'(\d+)\s*year', s)
    if m:
        v = float(max(int(x) for x in m))
        return v, v
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
             "twenty": 20, "thirty": 30}
    for w, n in words.items():
        if re.search(r'\b' + w + r'\b\s+year', s):
            return float(n), float(n)
    # defined-maturity funds: BulletShares/iBonds <year>
    m = re.findall(r'\b(20[2-9]\d)\b', s)
    if m and ("term" in s or "bulletshares" in s or "ibonds" in s):
        n = max(0.0, max(int(x) for x in m) - 2026)
        return n, n
    return None


def _asset_class(s):
    if re.search(r'\bhigh[\s-]?yield\b|fallen angel|\bccc\b', s):
        return "hy"
    if "tips" in s or "inflation protected" in s or "inflation-protected" in s:
        return "tips"
    if re.search(r'\bmuni|municipal|tax[\s-]?exempt|tax[\s-]?aware', s):
        return "muni"
    if "emerging market" in s or " em " in s:
        return "em"
    if re.search(r'treasury|govt|government|sovereign|strips', s):
        return "treasury"
    if "aggregate" in s or "core" in s or "total bond" in s:
        return "agg"
    if "investment grade" in s or "corporate" in s or "credit" in s:
        return "ig"
    return "generic"


def estimate_duration_from_name(name):
    """Approximate effective duration in years from the fund name, or None."""
    if not name:
        return None
    s = " " + str(name).lower() + " "

    # Floating rate / senior loans / CLOs reset coupons -> ~zero rate duration
    if re.search(r'floating[\s-]?rate|variable rate|senior loan|bank loan|'
                 r'leveraged loan|\bclo\b', s):
        return 0.2

    band = _maturity_band(s)
    if band is None:
        return None
    low, high = band
    mid = (low + high) / 2.0

    # Zero-coupon / STRIPS: duration ~= maturity
    if "zero" in s or "strips" in s:
        return round(mid, 2)

    y = _YIELD_BY_CLASS[_asset_class(s)]
    dur = _macaulay_par(mid, y)
    # high-yield bonds are usually callable -> shorten a touch
    if _asset_class(s) == "hy":
        dur *= 0.9
    return round(dur, 2)


# ===========================================================================
# Layer 3 -- representative duration per style bucket (last resort)
# ===========================================================================
_STYLE_DURATION = {
    "Money Market": 0.1, "High Interest Savings Account": 0.1,
    "Low Risk Bank Deposit": 0.1,
    "Ultra Short-Low Risk": 0.4, "Ultra Short Term Bond": 0.6,
    "Short Term Government Bond": 1.9, "Short Term High Quality": 2.5,
    "Short Term Bond": 2.5, "Short Term Mid Quality": 2.5,
    "Short Term Low Quality": 0.3, "Short Term High Yield Bond": 2.0,
    "Treasury Bond": 6.5,
    "Intermediate Term Government Bond": 5.5, "Intermediate Term Bond": 6.0,
    "Intermediate Term High Quality": 6.0, "Intermediate Term Mid Quality": 6.5,
    "Intermediate Term Low Quality": 6.5, "Investment Grade Bond": 6.0,
    "Long Term Government Bond": 16.0, "Long Term Bond": 13.0,
    "Long Term High Quality": 13.0, "Long Term Mid Quality": 12.0,
    "High Yield Bond": 3.5, "Preferred Stock": 5.0, "Multi Alternative": 4.0,
    "Real Estate": None, "Equity": None, "Commodity": None,
    "Cryptocurrency": None, "Unknown": None,
}


def estimate_duration_from_style(style):
    return _STYLE_DURATION.get(style)


# ===========================================================================
# Orchestrator + simple JSON cache
# ===========================================================================
_CACHE_PATH = "duration_cache.json"


def _load_cache():
    if os.path.exists(_CACHE_PATH):
        try:
            return json.load(open(_CACHE_PATH))
        except Exception:
            return {}
    return {}


def _save_cache(cache):
    try:
        json.dump(cache, open(_CACHE_PATH, "w"), indent=2)
    except Exception:
        pass


def get_duration(ticker, name=None, use_yahoo=True, use_cache=True):
    """Return {'ticker','duration','source','confidence'}.

    source     : 'yahoo' | 'name_estimate' | 'style_estimate' | None
    confidence : 'high'  | 'medium'        | 'low'            | None
    """
    ticker = (ticker or "").strip().upper()
    cache = _load_cache() if use_cache else {}
    if use_cache and ticker in cache:
        return cache[ticker]

    dur, source, conf = None, None, None

    if use_yahoo:
        dur = get_duration_yahoo(ticker)
        if dur is not None:
            source, conf = "yahoo", "high"

    if dur is None and name is not None:
        dur = estimate_duration_from_name(name)
        if dur is not None:
            source, conf = "name_estimate", "medium"

    if dur is None and name is not None and classify_etf_name is not None:
        dur = estimate_duration_from_style(classify_etf_name(name))
        if dur is not None:
            source, conf = "style_estimate", "low"

    result = {"ticker": ticker, "duration": dur,
              "source": source, "confidence": conf}
    if use_cache:
        cache[ticker] = result
        _save_cache(cache)
    return result

