import yfinance as yf
import numpy as np
import pandas as pd
from utils.logger import logger

def fetch_prices(symbols: list, period: str = "3y",
                 start: str = None, end: str = None) -> pd.DataFrame:
    """Fetch historical close prices, one column per ticker.

    Pass `start`/`end` (YYYY-MM-DD) to pull a fixed calendar window instead of a
    trailing `period` — used by the rate-hike stress test, which needs the 2022
    window regardless of how far back the optimizer's common window reaches.
    """
    prices = pd.DataFrame()
    use_window = bool(start or end)
    for ticker in symbols:
        try:
            logger.info(f"Fetching data for {ticker}")
            hist = (yf.Ticker(ticker).history(start=start, end=end)
                    if use_window else yf.Ticker(ticker).history(period=period))
            if hist.empty:
                logger.warning(f"No historical data for {ticker}, skipping")
                continue
            hist = hist[["Close"]].rename(columns={"Close": ticker})
            prices = pd.concat([prices, hist], axis=1)
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            continue
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