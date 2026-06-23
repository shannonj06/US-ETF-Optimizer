import pandas as pd
import numpy as np


def get_portfolio_metrics(
    portfolio: pd.DataFrame,
    returns: pd.DataFrame,
    correlation_matrix: pd.DataFrame,
    risk_free_rate: float = 0.04,
) -> pd.DataFrame:
    """
    portfolio : DataFrame with 'ETF' and 'Weight' columns (optimizer output).
    returns   : DataFrame of daily returns, columns = tickers.
    correlation_matrix : returns.corr() or equivalent.
    Returns a single-column DataFrame (index = metric name) suitable for printing.
    """
    weights = (
        portfolio.set_index("ETF")["Weight"]
        .reindex(returns.columns)
        .fillna(0)
        .values
    )

    port_returns = returns.values @ weights

    # ── return / risk ──────────────────────────────────────────────────────────
    n_years = len(port_returns) / 252
    cum_return = np.prod(1 + port_returns)
    annual_return = cum_return ** (1 / n_years) - 1

    annualized_vol = port_returns.std() * np.sqrt(252)

    # ── drawdown ───────────────────────────────────────────────────────────────
    cumulative = np.cumprod(1 + port_returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / (running_max + 1e-8)
    max_drawdown = abs(drawdowns.min())

    # ── ratios ─────────────────────────────────────────────────────────────────
    excess = annual_return - risk_free_rate
    sharpe_ratio = excess / annualized_vol if annualized_vol != 0 else 0.0

    daily_rf = (1 + risk_free_rate) ** (1 / 252) - 1
    downside = port_returns[port_returns < daily_rf] - daily_rf
    downside_vol = np.sqrt(np.mean(downside ** 2)) * np.sqrt(252) if len(downside) > 0 else 1e-8
    sortino_ratio = excess / downside_vol if downside_vol != 0 else 0.0

    calmar_ratio = annual_return / max_drawdown if max_drawdown != 0 else 0.0

    # ── tail risk ──────────────────────────────────────────────────────────────
    var_95 = -np.percentile(port_returns, 5)
    tail = port_returns[port_returns <= -var_95]
    cvar_95 = -tail.mean() if len(tail) > 0 else var_95

    # ── concentration ──────────────────────────────────────────────────────────
    hhi = float(np.sum(weights ** 2))

    active = portfolio.loc[portfolio["Weight"] > 0, "ETF"].tolist()
    if len(active) > 1:
        corr_sub = correlation_matrix.loc[active, active].values
        n = len(active)
        upper_tri = corr_sub[np.triu_indices(n, k=1)]
        average_correlation = float(upper_tri.mean())
    else:
        average_correlation = 1.0

    # ── diversification ratio ──────────────────────────────────────────────────
    asset_vols = returns.std().values * np.sqrt(252)
    diversification_ratio = (
        float(weights @ asset_vols) / annualized_vol if annualized_vol != 0 else 1.0
    )

    # ── beta vs equal-weighted universe ────────────────────────────────────────
    mkt_returns = returns.values.mean(axis=1)
    cov_pm = np.cov(port_returns, mkt_returns)
    beta = cov_pm[0, 1] / cov_pm[1, 1] if cov_pm[1, 1] != 0 else 1.0

    metrics = {
        "Annual Return":          f"{annual_return:.2%}",
        "Annual Volatility":      f"{annualized_vol:.2%}",
        "Sharpe Ratio":           f"{sharpe_ratio:.3f}",
        "Sortino Ratio":          f"{sortino_ratio:.3f}",
        "Calmar Ratio":           f"{calmar_ratio:.3f}",
        "Max Drawdown":           f"{max_drawdown:.2%}",
        "VaR 95% (daily)":        f"{var_95:.3%}",
        "CVaR 95% (daily)":       f"{cvar_95:.3%}",
        "Beta (vs EW universe)":  f"{beta:.3f}",
        "HHI":                    f"{hhi:.4f}",
        "Avg Pairwise Corr":      f"{average_correlation:.4f}",
        "Diversification Ratio":  f"{diversification_ratio:.4f}",
    }

    return pd.DataFrame.from_dict(metrics, orient="index", columns=["Value"])
