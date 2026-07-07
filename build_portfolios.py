"""End-to-end portfolio build pipeline, isolated from main.py.

main.py also pulls in matplotlib-based plotting / Monte-Carlo modules that are
only used by its CLI main(). Importing those from inside `streamlit run` is what
caused the import issues, so the frontend imports build_portfolios from here
instead — this module only imports what the pipeline actually needs.
"""

import copy

import numpy as np
import pandas as pd

from scoring.score_norm_select import select_top_etfs
from config.profiles import PORTFOLIO_PROFILES
from scoring.metrics import fetch_prices, returns_matrix
from Optimizer_Class.optimizer2 import portfolio_optimizer, shrink_covariance
from Optimizer_Class.optimizer_weights import OPTIMIZER_CONFIG
from Optimizer_Class.hrp_optimization import hrp_allocate, hrp_core4
from Optimizer_Class.get_portfolio_metrics import get_portfolio_metrics

# MongoDB collection holding the screening universe (populated by mongoDB.py).
MONGO_DB, MONGO_COLLECTION = "etf_data", "US_ETF_DATA"

# Rate-hike stress window (Fed hiking cycle of 2022).
_RH_START, _RH_END = "2022-01-01", "2022-12-31"


def load_etf_data():
    """Load the ETF screening universe from MongoDB instead of the CSV.

    Reads every document from `etf_data.US_ETF_DATA` (refreshed by mongoDB.py)
    and returns a DataFrame with the same columns the CSV had. The Mongo `_id`
    is excluded so downstream code is unchanged. Connecting here (not at import
    time) keeps the frontend importable even if the database is unreachable.
    """
    import certifi
    from pymongo import MongoClient
    from configuration import MONGODB_URL

    if not MONGODB_URL:
        raise RuntimeError(
            "MONGODB_URL is not set. On Streamlit Cloud, add it under "
            "Manage app -> Settings -> Secrets; locally it comes from the .env file."
        )

    # tlsCAFile pins the CA bundle so the Atlas handshake works in cloud venvs;
    # the short timeout turns an unreachable DB into a fast, clear error.
    client = MongoClient(
        MONGODB_URL,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
    )
    try:
        docs = list(client[MONGO_DB][MONGO_COLLECTION].find({}, {"_id": 0}))
    finally:
        client.close()
    if not docs:
        raise RuntimeError(
            f"No ETF data in MongoDB ({MONGO_DB}.{MONGO_COLLECTION} is empty). "
            "Run mongoDB.py to populate it."
        )
    return pd.DataFrame(docs)


def _stress_window_returns(tickers, start=_RH_START, end=_RH_END):
    """Daily returns covering the rate-hike window, fetched DIRECTLY from Yahoo
    rather than sliced out of the optimizer's common 5y window.

    The optimizer's returns frame is the intersection of every ticker's history,
    so it starts after 2022 the moment the universe contains any post-2022 ETF —
    which is why the stress chart was always coming back empty on the frontend.
    Here we pull a slightly padded window per ticker, keep only the funds that
    actually traded across the whole window, and return their 2022 returns.
    """
    # pad the front so pct_change has a prior close on the first stress day
    pad_start = (pd.Timestamp(start) - pd.Timedelta(days=20)).strftime("%Y-%m-%d")
    pad_end = (pd.Timestamp(end) + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    px = fetch_prices(list(tickers), start=pad_start, end=pad_end)
    if px.empty:
        return pd.DataFrame()
    px = px.dropna(axis=1, how="any")          # drop funds not trading the full window
    rets = px.pct_change().dropna()
    if not len(rets.index):
        return pd.DataFrame()
    if getattr(rets.index, "tz", None) is not None:
        rets.index = rets.index.tz_localize(None)  # tz-naive so string slicing is exact
    return rets.loc[start:end]


def _rate_hike_fig(stress_rets, weights_df, initial_value=1_000_000):
    """Rate-hike stress figure for one allocation, or None if the held names have
    no usable 2022 history. Weights are renormalized across the surviving names."""
    if stress_rets is None or stress_rets.empty:
        return None
    from models.monte_carlo import rate_hike_stress_test
    w = (weights_df.set_index("ETF")["Weight"]
         .reindex(stress_rets.columns).fillna(0.0))
    if w.sum() <= 0:                           # none of the held ETFs traded in 2022
        return None
    w = w / w.sum()
    benchmark = stress_rets.mean(axis=1)       # equal-weighted across surviving names
    try:
        *_, fig = rate_hike_stress_test(stress_rets, w.values, initial_value,
                                        benchmark, start=_RH_START, end=_RH_END,
                                        show=False)
    except ValueError:
        return None
    return fig


def evaluate_custom_weights(weights, period="5y", rf=0.04):
    """Metrics + charts for an EXPLICIT allocation across any number of tickers —
    the frontend port of main_portfolio.evaluate_weights, with no optimization.

    weights : {ticker: weight}; need not sum to 1 (normalized here).
    Returns {"weights", "metrics", "dropped", "figs", "window"}.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from models.monte_carlo import (
        monte_carlo_simulation, monte_carlo_metrics, back_testing,
    )

    tickers = list(weights)
    price_df = fetch_prices(tickers, period)
    returns_df = (returns_matrix(price_df)
                  .replace([np.inf, -np.inf], np.nan)
                  .dropna(axis=1))
    dropped = [t for t in tickers if t not in returns_df.columns]
    if returns_df.shape[1] == 0 or not len(returns_df.index):
        raise ValueError("No overlapping price history for the given tickers.")

    w = pd.Series({t: float(weights[t]) for t in returns_df.columns})
    if w.sum() != 0:
        w = w / w.sum()
    weights_df = (w.rename("Weight").rename_axis("ETF").reset_index()
                  .sort_values("Weight", ascending=False).reset_index(drop=True))

    corr = returns_df.corr()
    metrics = get_portfolio_metrics(weights_df, returns_df, corr, risk_free_rate=rf)

    benchmark = returns_df.mean(axis=1)
    w_arr = (weights_df.set_index("ETF")["Weight"]
             .reindex(returns_df.columns).fillna(0).values)
    paths = monte_carlo_simulation(returns_df, w_arr, 1_000_000, years=5, simulations=1000)
    _, mc_fig, mc_dist_fig = monte_carlo_metrics(paths, 1_000_000, show=False)
    *_, bt_fig = back_testing(returns_df, w_arr, 1_000_000, benchmark, show=False)
    rh_fig = _rate_hike_fig(_stress_window_returns(returns_df.columns.tolist()),
                            weights_df)

    figs = {
        "monte_carlo":      mc_fig,
        "monte_carlo_dist": mc_dist_fig,
        "backtest":         bt_fig,
        "rate_hike":        rh_fig,
    }
    plt.close("all")
    return {
        "weights": weights_df,
        "metrics": metrics,
        "dropped": dropped,
        "figs": figs,
        "window": (returns_df.index[0].date(), returns_df.index[-1].date()),
    }


def build_portfolios(profile, screening=None, score_weights=None,
                     optimizer_weights=None, period="5y", top_n=40):
    """End-to-end pipeline for the frontend: from a profile + optional user
    overrides, run SLSQP / CVXPY / HRP and return everything a page needs.

    profile           : "conservative" | "enhanced" | "strategic"
    screening         : dict overriding aum_min / max_expense / max_duration
    score_weights     : dict overriding the per-metric selection weights
    optimizer_weights : dict overriding the SLSQP objective weights (auto-renormalized)

    Returns a dict: slsqp / cvxpy / hrp weight DataFrames, plus returns_df, corr,
    and top_etf_df so the caller can compute metrics / charts.
    """
    # copy the shared config so frontend overrides never mutate the module globals
    profiles = copy.deepcopy(PORTFOLIO_PROFILES)
    config = copy.deepcopy(OPTIMIZER_CONFIG)
    if screening:
        profiles[profile].update(screening)
    if score_weights:
        profiles[profile]["score_weights"].update(score_weights)
    if optimizer_weights:
        sw = {**config[profile]["slsqp_weights"], **optimizer_weights}
        total = sum(sw.values())  # frontend edits may not sum to 1 -> renormalize so SLSQP doesn't reject
        config[profile]["slsqp_weights"] = {k: v / total for k, v in sw.items()} if total else sw

    # 1. select the universe (applies the screening gates + scoring weights above)
    df = load_etf_data()
    top_etf_df = select_top_etfs(df, profiles, profile, top_n)

    # 2. prices -> returns; drop tickers with gaps, then realign top_etf_df to survivors
    #    (the optimizer raises if yields/expenses don't cover every returns column)
    price_df = fetch_prices(top_etf_df["Symbol"].tolist(), period)
    returns_df = returns_matrix(price_df).replace([np.inf, -np.inf], np.nan).dropna(axis=1)
    top_etf_df = top_etf_df[top_etf_df["Symbol"].isin(returns_df.columns)].reset_index(drop=True)

    # 3. build the optimizer and run the three methods
    yield_df = top_etf_df.set_index("Symbol")["YIELD"]
    expense_df = top_etf_df.set_index("Symbol")["ER"] / 100
    optimizer = portfolio_optimizer(returns_df, config, yield_df, expense_df, top_etf_df)

    slsqp_df, _ = optimizer.run_custom_slsqp_optimization(None, profile)
    cvxpy_df, _ = optimizer.run_cvxpy_optimization(profile)
    hrp_weights = hrp_allocate(shrink_covariance(returns_df), method="ward", plot=False)
    hrp_df = (
        hrp_weights.rename("Weight")
        .rename_axis("ETF")
        .reset_index()
        .sort_values("Weight", ascending=False)
        .reset_index(drop=True)
    )
    slsqp4, _ = optimizer.run_slsqp_core_k(profile, k=4)
    cvxpy4, _ = optimizer.run_cvxpy_cardinality(profile, k=4)
    hrp4_w = hrp_core4(shrink_covariance(returns_df), k=4)
    hrp4_df = hrp4_w.rename("Weight").rename_axis("ETF").reset_index()

    # 4. performance / risk metrics for each portfolio (3 full + 3 core-4)
    corr = returns_df.corr()

    # 5. charts for each portfolio — matplotlib Figures the frontend renders with
    #    st.pyplot(fig). Imported HERE (not at module top) so importing
    #    build_portfolios from the Streamlit frontend stays light; Agg renders to
    #    memory with no GUI window (a GUI backend would hang under Streamlit).
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from models.monte_carlo import (
        monte_carlo_simulation,
        monte_carlo_metrics,
        back_testing,
        walk_forward_backtest,
    )

    benchmark = returns_df.mean(axis=1)   # equal-weighted universe

    # Fetch the 2022 rate-hike window ONCE for the whole universe, then reuse it
    # for every portfolio's stress chart (avoids re-downloading per allocation).
    stress_rets = _stress_window_returns(returns_df.columns.tolist())

    def weights_array(weights_df):
        return (weights_df.set_index("ETF")["Weight"]
                .reindex(returns_df.columns).fillna(0).values)

    # walk-forward re-optimizes SLSQP each window and ignores the given weights, so
    # it's profile-level — compute once and share the same figure across all six.
    _, wf_fig = walk_forward_backtest(returns_df, yield_df, benchmark, expense_df,
                                      top_etf_df, config, profile, 1_000_000, show=False)

    def make_figs(weights_df):
        w = weights_array(weights_df)
        paths = monte_carlo_simulation(returns_df, w, 1_000_000, years=5, simulations=1000)
        _, mc_fig, mc_dist_fig = monte_carlo_metrics(paths, 1_000_000, show=False)
        *_, bt_fig = back_testing(returns_df, w, 1_000_000, benchmark, show=False)
        rh_fig = _rate_hike_fig(stress_rets, weights_df)
        return {
            "monte_carlo":      mc_fig,
            "monte_carlo_dist": mc_dist_fig,
            "backtest":         bt_fig,
            "walk_forward":     wf_fig,
            "rate_hike":        rh_fig,
        }

    result = {
        "profile": profile,
        "config": config,            # deep-copied config w/ frontend overrides applied
        "slsqp": slsqp_df,
        "cvxpy": cvxpy_df,
        "hrp": hrp_df,
        "returns_df": returns_df,
        "corr": corr,
        "top_etf_df": top_etf_df,
        "slsqp4": slsqp4,
        "cvxpy4": cvxpy4,
        "hrp4": hrp4_df,
        "slsqp_metrics": get_portfolio_metrics(slsqp_df, returns_df, corr),
        "cvxpy_metrics": get_portfolio_metrics(cvxpy_df, returns_df, corr),
        "hrp_metrics": get_portfolio_metrics(hrp_df, returns_df, corr),
        "slsqp4_metrics": get_portfolio_metrics(slsqp4, returns_df, corr),
        "cvxpy4_metrics": get_portfolio_metrics(cvxpy4, returns_df, corr),
        "hrp4_metrics": get_portfolio_metrics(hrp4_df, returns_df, corr),
        "slsqp_figs": make_figs(slsqp_df),
        "cvxpy_figs": make_figs(cvxpy_df),
        "hrp_figs": make_figs(hrp_df),
        "slsqp4_figs": make_figs(slsqp4),
        "cvxpy4_figs": make_figs(cvxpy4),
        "hrp4_figs": make_figs(hrp4_df),
    }

    # drop the Figures from pyplot's registry so they don't leak across Streamlit
    # reruns; the objects stay in `result` and still render fine via st.pyplot().
    plt.close("all")
    return result


