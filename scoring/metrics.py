import time

import yfinance as yf
import numpy as np
import pandas as pd
from utils.logger import logger

def fetch_prices(symbols: list, period: str = "3y",
                 start: str = None, end: str = None,
                 retries: int = 2, pause: float = 1.0) -> pd.DataFrame:
    """Fetch historical close prices, one column per ticker.

    Pass `start`/`end` (YYYY-MM-DD) to pull a fixed calendar window instead of a
    trailing `period` — used by the rate-hike stress test, which needs the 2022
    window regardless of how far back the optimizer's common window reaches.

    Yahoo throttles heavy callers (much more aggressively from datacenter IPs
    like Railway's), and a throttled response comes back empty or truncated
    rather than as an error. Two mitigations:

      * `retries` with a linear backoff, so a transient empty response doesn't
        silently drop the ticker from the universe.
      * Index normalization to tz-naive calendar dates. Raw yfinance indices are
        tz-aware and can differ across tickers; concatenating them unaligned
        produces a frame where every row has a NaN somewhere, which the caller's
        .dropna() then wipes out entirely -> a 0-row returns matrix.
    """
    prices = pd.DataFrame()
    use_window = bool(start or end)
    for ticker in symbols:
        hist = None
        for attempt in range(retries + 1):
            try:
                logger.info(f"Fetching data for {ticker}")
                h = (yf.Ticker(ticker).history(start=start, end=end)
                     if use_window else yf.Ticker(ticker).history(period=period))
                if not h.empty:
                    hist = h
                    break
                logger.warning(f"Empty response for {ticker} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Error fetching data for {ticker} "
                             f"(attempt {attempt + 1}): {e}")
            if attempt < retries:
                time.sleep(pause * (attempt + 1))

        if hist is None:
            logger.warning(f"No historical data for {ticker}, skipping")
            continue

        col = hist[["Close"]].rename(columns={"Close": ticker})
        idx = col.index
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        col.index = idx.normalize()                       # align on calendar dates
        col = col[~col.index.duplicated(keep="last")]
        prices = col if prices.empty else prices.join(col, how="outer")
    return prices
        
    
def returns_matrix(price_df: pd.DataFrame) -> pd.DataFrame:
    """Convert price data to returns matrix."""
    return price_df.pct_change().dropna()

def calculate_all_metrics(
    returns: pd.Series,
    rf: float = 0.03
) -> dict:
    ann_ret = (1 + returns).prod() ** (252 / len(returns)) - 1
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = (
        (ann_ret - rf) / ann_vol
        if ann_vol > 1e-10 else np.nan
    )
    downside_vol = (
        returns[returns < 0].std() * np.sqrt(252)
    )
    sortino = (
        (ann_ret - rf) / downside_vol
        if downside_vol > 1e-10 else np.nan
    )
    wealth = (1 + returns).cumprod()
    peak = wealth.cummax()

    drawdowns = (wealth - peak) / peak

    max_dd = drawdowns.min()
    avg_dd = drawdowns.mean()

    calmar = (
        ann_ret / abs(max_dd)
        if abs(max_dd) > 1e-10 else np.nan
    )

    var_95 = np.percentile(returns, 5)
    cvar_95 = returns[returns <= var_95].mean()

    return {
        "annualized_return": ann_ret,
        "annualized_volatility": ann_vol,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_dd,
        "average_drawdown": avg_dd,
        "calmar_ratio": calmar,
        "var_95": var_95,
        "cvar_95": cvar_95,
        "skewness": returns.skew(),
        "kurtosis": returns.kurtosis()
    }