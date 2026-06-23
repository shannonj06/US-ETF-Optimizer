import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent
OUT_CSV = BASE_DIR / "data_sourcing" / "US_Final_ETF_Data.csv"

# Import the helpers from the data_sourcing package (resolves cleanly for the
# type checker). We ALSO put data_sourcing on sys.path so durationSourcing's own
# internal `from style_mapping import ...` resolves at runtime — otherwise its
# style-estimate layer silently disables itself.
sys.path.insert(0, str(BASE_DIR / "data_sourcing"))
from data_sourcing.style_mapping import classify_etf_name     # noqa: E402
from data_sourcing.durationSourcing import get_duration       # noqa: E402

OUTPUT_COLS = ["Symbol", "BETA", "Name", "AUM", "YIELD", "SHARPE", "MAX_DD",
               "ANNUAL_VOL", "STYLE", "AVG_VOLUME_30", "DURATION", "ER"]


def load_etf_universe():
    """Symbol + Name for the universe to refresh, from the static seed file."""
    excel_path = BASE_DIR / "datasets" / "US_ETF_DF.xlsx - US ETF Data.csv"
    df = pd.read_csv(excel_path)
    df.columns = df.columns.str.strip()
    df = df[["Symbol", "Name"]].copy()
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    return df.dropna(subset=["Symbol", "Name"]).drop_duplicates("Symbol")


def compute_beta(etf_returns, market_returns):
    """Cov(etf, mkt) / Var(mkt) over overlapping dates. NaN if too short."""
    df = pd.concat([etf_returns, market_returns], axis=1, join="inner").dropna()
    if len(df) < 2:
        return np.nan
    df.columns = ["etf", "mkt"]
    var = df["mkt"].var()
    return df["etf"].cov(df["mkt"]) / var if var > 0 else np.nan


def expense_ratio(etf, info):
    """Two-path expense-ratio lookup: structured fund data, then .info."""
    val = None
    try:
        ov = etf.funds_data.fund_overview
        if isinstance(ov, dict):
            for k in ("expense_ratio", "expenseRatio", "annualReportExpenseRatio"):
                if ov.get(k) not in (None, ""):
                    val = ov[k]
                    break
    except Exception:
        pass
    if val is None:
        for k in ("annualReportExpenseRatio", "netExpenseRatio", "expenseRatio"):
            if info.get(k) not in (None, ""):
                val = info[k]
                break
    return float(val) if val is not None else np.nan


def _years(period):
    """Parse '1y'/'3y'/'5y' -> int years (defaults to 1)."""
    p = str(period).lower().strip()
    return int(p[:-1]) if p.endswith("y") and p[:-1].isdigit() else 1


def fetch_metrics(ticker, name, market_returns, period="1y", beta_period="5y",
                  rf=0.04):
    """All refreshable metrics for one ticker. None if no data.

    Beta is computed over `beta_period` (a longer window lands closer to a
    long-window source); return/vol/Sharpe/drawdown use the trailing `period`.
    """
    etf = yf.Ticker(ticker)
    hist = etf.history(period=beta_period)   # long history covers beta + the slice
    if hist.empty:
        return None
    info = etf.info or {}

    close = hist["Close"]
    # beta over the full long window vs the market (also fetched over beta_period)
    beta = compute_beta(close.pct_change().dropna(), market_returns)

    # standard metrics over the trailing `period` slice (preserves the 1y convention)
    cutoff = close.index[-1] - pd.DateOffset(years=_years(period))
    close_p = close[close.index >= cutoff]
    daily = close_p.pct_change().dropna()

    annual_return = (1 + daily.mean()) ** 252 - 1
    annual_vol = daily.std() * np.sqrt(252)
    sharpe = (annual_return - rf) / annual_vol if annual_vol > 0 else np.nan

    running_max = close_p.cummax()
    max_drawdown = ((close_p - running_max) / running_max).min()

    one_year_ago = close.index[-1] - pd.DateOffset(years=1)
    divs = etf.dividends
    ttm_div = divs[divs.index >= one_year_ago].sum() if len(divs) else 0.0
    price = close.iloc[-1]
    dividend_yield = ttm_div / price if price > 0 else np.nan

    aum = info.get("totalAssets", np.nan)
    vol30 = hist["Volume"].tail(30).mean()
    er = expense_ratio(etf, info)
    style = classify_etf_name(name)
    try:
        d = get_duration(ticker, name)
        duration = d["duration"] if d else np.nan
    except Exception:
        duration = np.nan

    def r(x, n):
        return round(x, n) if pd.notna(x) else np.nan

    return {
        "Symbol":        ticker,
        "BETA":          r(beta, 4),
        "Name":          name,
        "AUM":           r(aum, 2),
        "YIELD":         r(dividend_yield, 4),
        "SHARPE":        r(sharpe, 4),
        "MAX_DD":        r(max_drawdown, 4),
        "ANNUAL_VOL":    r(annual_vol, 2),
        "STYLE":         style,
        "AVG_VOLUME_30": r(vol30, 2),
        "DURATION":      duration,
        "ER":            r(er, 2),
    }


def update(period="1y", beta_period="5y", benchmark="SPY", rf=0.04, symbols=None,
           out_csv=OUT_CSV, sleep=1.0, write=True, backup=True):
    """Refresh every ticker and (optionally) write the CSV.

    period      : window for return/vol/Sharpe/drawdown ("1y"/"3y"/"5y").
    beta_period : window for beta only (default 5y — closest to the prior source).
    benchmark   : market leg for beta (default SPY).
    symbols     : optional subset; defaults to the whole universe.
    write       : set False to compute without touching disk (tests/cloud dry-run).
    backup      : if writing, copy the existing CSV to a timestamped .bak first.

    Returns the refreshed DataFrame.
    """
    universe = load_etf_universe()
    name_by_sym = dict(zip(universe["Symbol"], universe["Name"]))
    tickers = symbols if symbols is not None else universe["Symbol"].tolist()

    market = (
        yf.Ticker(benchmark).history(period=beta_period)["Close"]
        .pct_change().dropna()
    )
    if market.empty:
        raise RuntimeError(f"no benchmark history for {benchmark}")

    records = []
    for sym in tickers:
        try:
            print(f"Updating {sym}")
            rec = fetch_metrics(sym, name_by_sym.get(sym, ""), market,
                                period, beta_period, rf)
            if rec:
                records.append(rec)
            else:
                print(f"  [warn] no price history for {sym}")
            time.sleep(sleep)
        except Exception as e:
            print(f"  [error] {sym}: {e}")

    if not records:
        raise RuntimeError("no tickers updated — nothing to write")

    df = pd.DataFrame(records)[OUTPUT_COLS]
    if write:
        if backup and Path(out_csv).exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = Path(out_csv).with_name(f"{Path(out_csv).stem}.{stamp}.bak.csv")
            shutil.copy(out_csv, bak)
            print(f"backed up previous CSV -> {bak.name}")
        df.to_csv(out_csv, index=False)
        print(f"wrote {len(df)} rows -> {out_csv}")
    return df


if __name__ == "__main__":
    update()
