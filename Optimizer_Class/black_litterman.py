from pypfopt.black_litterman import BlackLittermanModel
from pypfopt import risk_models
import pandas as pd
import numpy as np
from Optimizer_Class.optimizer_weights import OPTIMIZER_CONFIG


def black_litterman_returns(
    returns: pd.DataFrame,
    top_etf_df: pd.DataFrame,
    use_views: bool = True,
    # ±3% views on ultra-short bond ETFs (~0.5% vol) swamp the equilibrium prior
    # and the risk term downstream; ±0.5% per z-score keeps views in scale.
    max_view: float = 0.005,
) -> pd.Series:
    # drop tickers with any NaN or inf (incomplete history, or zero-price pct_change artifacts)
    clean = returns.replace([np.inf, -np.inf], np.nan).dropna(axis=1)

    S = risk_models.CovarianceShrinkage(clean, returns_data=True).ledoit_wolf()

    # align market caps and views to the surviving tickers only
    market_caps = top_etf_df.set_index("Symbol")["AUM"].reindex(clean.columns).dropna()

    views = {}
    if use_views and "score" in top_etf_df.columns:
        scores = top_etf_df.set_index("Symbol")["score"].reindex(clean.columns).dropna()
        std = scores.std()
        if std > 0:
            normalized = (scores - scores.mean()) / std
            views = (normalized * max_view).to_dict()

    bl = BlackLittermanModel(
        cov_matrix=S,
        pi="market",
        market_caps=market_caps,
        absolute_views=views,
        risk_aversion=OPTIMIZER_CONFIG["bl"]["delta"],
        tau=OPTIMIZER_CONFIG["bl"]["tau"],
    )
    return bl.bl_returns()
