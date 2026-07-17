import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf
from Optimizer_Class.optimizer2 import portfolio_optimizer

# Shared "growth of $1"-style palette (portfolio vs. benchmark), used by
# back_testing()'s growth panel and return_distribution_chart().
_PORTFOLIO_COLOR = "#8BAE46"   # olive green
_BENCHMARK_COLOR = "#4D4D4D"   # dark gray


def _drawdown(path: np.ndarray) -> np.ndarray:
    peak = np.maximum.accumulate(path)
    return (path - peak) / (peak + 1e-10)


def _style_growth_axes(ax):
    """Clean editorial look shared by the growth-of-$1 style charts: no top/right
    spines, dashed horizontal gridlines only, light axis lines."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#999999")
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)


def monte_carlo_simulation(
    returns: pd.DataFrame,
    weights: np.ndarray,
    initial_value: float,
    years: int,
    simulations: int,
) -> np.ndarray:
    mean_returns = returns.mean().values
    cov_matrix   = returns.cov().values
    days         = years * 252
    paths        = np.zeros((simulations, days + 1))
    paths[:, 0]  = initial_value

    for sim in range(simulations):
        daily = np.random.multivariate_normal(mean_returns, cov_matrix, size=days)
        paths[sim, 1:] = initial_value * np.cumprod(1 + daily @ weights)

    return paths


def monte_carlo_metrics(paths: np.ndarray, initial_value: float, show: bool = True) -> tuple:
    ending = paths[:, -1]
    metrics = {
        "expected_ending": float(np.mean(ending)),
        "median_ending":   float(np.median(ending)),
        "best_case":       float(np.max(ending)),
        "worst_case":      float(np.min(ending)),
        "prob_loss":       float(np.mean(ending < initial_value)),
        "p5_ending":       float(np.percentile(ending, 5)),
        "p95_ending":      float(np.percentile(ending, 95)),
    }

    p5  = np.percentile(paths, 5,  axis=0)
    p95 = np.percentile(paths, 95, axis=0)
    x   = range(paths.shape[1])

    peaks = np.maximum.accumulate(paths, axis=1)
    dd    = (paths - peaks) / (peaks + 1e-10)
    dd_p5 = np.percentile(dd, 5, axis=0)

    # --- wealth + drawdown ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9), sharex=True)

    ax1.plot(paths.T, alpha=0.05, color="steelblue", linewidth=0.5)
    ax1.fill_between(x, p5, p95, alpha=0.2, color="steelblue", label="5th–95th pct")
    ax1.plot(paths.mean(axis=0),        color="green",  linewidth=2,   label="Expected")
    ax1.plot(np.median(paths, axis=0),  color="orange", linewidth=2,   label="Median")
    ax1.plot(paths[np.argmax(ending)],  color="blue",   linewidth=1.5, label="Best case")
    ax1.plot(paths[np.argmin(ending)],  color="red",    linewidth=1.5, label="Worst case")
    ax1.axhline(initial_value, color="black", linestyle="--", linewidth=2, label="Initial")
    text = (
        f"Expected: ${metrics['expected_ending']:,.0f}\n"
        f"Median:   ${metrics['median_ending']:,.0f}\n"
        f"Best:     ${metrics['best_case']:,.0f}\n"
        f"Worst:    ${metrics['worst_case']:,.0f}\n"
        f"P(loss):  {metrics['prob_loss']:.1%}"
    )
    ax1.text(1.02, 0.95, text, transform=ax1.transAxes, fontsize=11,
             verticalalignment="top",
             bbox=dict(facecolor="lightblue", alpha=0.5, boxstyle="round"))
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.set_title("5-Year Projection (1,000 Simulated Scenarios)")
    ax1.grid(alpha=0.3)
    ax1.legend()

    ax2.fill_between(x, dd_p5, 0, alpha=0.2, color="red", label="Worst 5% of scenarios")
    ax2.plot(dd.mean(axis=0),           color="red",     linewidth=2,   label="Average scenario")
    ax2.plot(dd[np.argmin(ending)],     color="darkred", linewidth=1,
             linestyle="--",                                             label="Worst scenario")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xlabel("Days Into the Future")
    ax2.set_ylabel("Decline From Peak")
    ax2.set_title("Simulated Declines From Peak Value")
    ax2.grid(alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    if show:
        plt.show()

    # --- ending value histogram ---
    fig2, ax3 = plt.subplots(figsize=(10, 5))
    ax3.hist(ending, bins=50, density=True, alpha=0.75, color="steelblue")
    ax3.axvline(metrics["expected_ending"], color="green",  linewidth=2,              label="Expected")
    ax3.axvline(metrics["median_ending"],   color="orange", linewidth=2,              label="Median")
    ax3.axvline(metrics["p5_ending"],       color="red",    linewidth=2, linestyle="--", label="Bottom 5% of outcomes")
    ax3.axvline(initial_value,              color="black",  linewidth=2, linestyle="--", label="Starting value")
    ax3.set_xlabel("Portfolio Value After 5 Years ($)")
    ax3.set_ylabel("Likelihood")
    ax3.set_title("Range of Possible 5-Year Outcomes")
    ax3.grid(alpha=0.3)
    ax3.legend()
    plt.tight_layout()
    if show:
        plt.show()

    return metrics, fig, fig2


def back_testing(
    portfolio_returns: pd.DataFrame,
    weights: np.ndarray,
    initial_value: float,
    benchmark_returns: pd.Series,
    show: bool = True,
) -> tuple:
    port_path  = initial_value * np.cumprod(1 + portfolio_returns.values @ weights)
    bench_path = initial_value * np.cumprod(1 + benchmark_returns.values)
    port_dd    = _drawdown(port_path)
    bench_dd   = _drawdown(bench_path)

    portfolio_return = port_path[-1]  / initial_value - 1
    benchmark_return = bench_path[-1] / initial_value - 1

    text = (
        f"Portfolio Return: {portfolio_return:.2%}\n"
        f"Benchmark Return: {benchmark_return:.2%}"
    )

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # "Growth of $1" style: both series filled from 0, benchmark drawn on top so
    # it reads as a base layer with the portfolio's excess growth shown above it
    # wherever the portfolio is ahead (falls back to plain overlap elsewhere).
    ax1.fill_between(portfolio_returns.index, 0, port_path,  color=_PORTFOLIO_COLOR, zorder=1)
    ax1.fill_between(benchmark_returns.index, 0, bench_path, color=_BENCHMARK_COLOR, zorder=2)
    ax1.plot(portfolio_returns.index, port_path,  color=_PORTFOLIO_COLOR, linewidth=0.8, zorder=3)
    ax1.plot(benchmark_returns.index, bench_path, color=_BENCHMARK_COLOR, linewidth=0.8, zorder=3)
    ax1.text(1.02, 0.95, text, transform=ax1.transAxes, fontsize=11,
             verticalalignment="top",
             bbox=dict(facecolor="lightblue", alpha=0.5, boxstyle="round"))
    ax1.set_ylabel("Value of $1 Invested")
    ax1.set_title("Growth of $1", loc="left", fontweight="bold")
    ax1.set_ylim(bottom=0)
    ax1.margins(x=0)
    _style_growth_axes(ax1)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=_PORTFOLIO_COLOR),
        plt.Rectangle((0, 0), 1, 1, color=_BENCHMARK_COLOR),
    ]
    ax1.legend(handles, ["Portfolio", "Benchmark"], loc="upper left",
               frameon=False, ncol=2, bbox_to_anchor=(0, 1.12))

    ax2.plot(portfolio_returns.index, port_dd,  color="purple", label="Portfolio Drawdown")
    ax2.plot(benchmark_returns.index, bench_dd, color="blue",   label="Benchmark Drawdown")
    ax2.fill_between(portfolio_returns.index, port_dd,  0, alpha=0.15, color="purple")
    ax2.fill_between(benchmark_returns.index, bench_dd, 0, alpha=0.15, color="blue")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Drawdown")
    ax2.set_title("Drawdown")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    if show:
        plt.show()

    return port_path, bench_path, fig


def _nice_step(raw_step: float) -> float:
    """Round a raw bucket width up to a human-friendly step (1/2/2.5/5 x10^n)."""
    if raw_step <= 0:
        return 0.01
    magnitude = 10 ** np.floor(np.log10(raw_step))
    for m in (1, 2, 2.5, 5, 10):
        if raw_step <= m * magnitude:
            return m * magnitude
    return 10 * magnitude


def _return_buckets(all_returns: np.ndarray, target_buckets: int = 7) -> list:
    """Build bucket edges sized to the ACTUAL spread of the data, instead of a
    fixed set of bands. A bond-heavy conservative portfolio might range 1%-6%
    annualized — fixed 10%-wide equity-scale buckets would dump nearly
    everything into one bin. Returns a list of (lo, hi, label) triples."""
    lo, hi = float(all_returns.min()), float(all_returns.max())
    if lo == hi:
        lo, hi = lo - 0.01, hi + 0.01
    step = _nice_step((hi - lo) / target_buckets)
    start = np.floor(lo / step) * step
    edges = [start]
    while edges[-1] < hi:
        edges.append(edges[-1] + step)

    decimals = 0 if step >= 0.01 else 1
    def fmt(v):
        return f"{v * 100:.{decimals}f}%"

    return [(edges[i], edges[i + 1], f"{fmt(edges[i])} to {fmt(edges[i + 1])}")
            for i in range(len(edges) - 1)]


def _bucket_counts(annualized_returns: np.ndarray, buckets: list) -> list:
    counts = []
    for i, (lo, hi, _) in enumerate(buckets):
        mask = (annualized_returns >= lo) & (annualized_returns <= hi if i == len(buckets) - 1
                                              else annualized_returns < hi)
        counts.append(int(mask.sum()))
    return counts


def return_distribution_chart(
    portfolio_returns: pd.DataFrame,
    weights: np.ndarray,
    benchmark_returns: pd.Series,
    window_years: int = 3,
    trading_days_per_year: int = 252,
    show: bool = True,
):
    """Bucket rolling `window_years`-annualized returns for the portfolio and an
    equal-weighted benchmark into return-range bins, and plot how many rolling
    periods fell in each bin — a distribution of outcomes rather than a single
    point-in-time return.
    """
    window = window_years * trading_days_per_year
    port_daily = portfolio_returns.values @ weights
    bench_daily = benchmark_returns.values

    n = len(port_daily)
    if n <= window:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "Not enough history for a rolling return distribution.",
                ha="center", va="center", transform=ax.transAxes, color="#666666")
        ax.axis("off")
        if show:
            plt.show()
        return fig

    def rolling_annualized(daily):
        path = np.cumprod(1 + daily)
        total = path[window:] / path[:-window]
        return total ** (trading_days_per_year / window) - 1

    port_ann = rolling_annualized(port_daily)
    bench_ann = rolling_annualized(bench_daily)

    # Buckets are sized to this data's own range (see _return_buckets), so the
    # chart always spreads meaningfully across its width regardless of whether
    # the portfolio is a low-volatility bond mix or a wide-swinging equity one.
    buckets = _return_buckets(np.concatenate([port_ann, bench_ann]))
    port_counts = _bucket_counts(port_ann, buckets)
    bench_counts = _bucket_counts(bench_ann, buckets)
    labels = [b[2] for b in buckets]

    x = np.arange(len(labels))
    bar_width = 0.38

    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 1.1), 5.5))
    port_bars = ax.bar(x - bar_width / 2, port_counts, bar_width, color=_PORTFOLIO_COLOR)
    bench_bars = ax.bar(x + bar_width / 2, bench_counts, bar_width, color=_BENCHMARK_COLOR)

    for bars in (port_bars, bench_bars):
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5, str(int(h)),
                        ha="center", va="bottom", fontsize=9, color="#333333")

    ax.set_title(f"How Often {window_years}-Year Returns Landed in Each Range", loc="left", fontweight="bold")
    ax.set_xlabel(f"{window_years}-Year Annualized Return")
    ax.set_ylabel(f"Number of {window_years}-Year Periods")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylim(bottom=0)
    _style_growth_axes(ax)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=_PORTFOLIO_COLOR),
        plt.Rectangle((0, 0), 1, 1, color=_BENCHMARK_COLOR),
    ]
    ax.legend(handles, ["Portfolio", "Benchmark"], loc="upper right", frameon=False)

    plt.tight_layout()
    if show:
        plt.show()

    return fig


def walk_forward_backtest(
    portfolio_returns: pd.DataFrame,
    etf_yields: pd.Series,
    benchmark_returns: pd.Series,
    etf_expenses: pd.Series,
    top_etf_df: pd.DataFrame,
    type_specific_weights: dict,
    key: str,
    initial_value: float,
    training_days: int = 252,
    testing_days: int = 63,
    show: bool = True,
) -> np.ndarray:
    path    = []
    indices = []
    portfolio_value = initial_value
    start = 0

    while start + training_days + testing_days <= len(portfolio_returns):
        train = portfolio_returns.iloc[start : start + training_days]
        test  = portfolio_returns.iloc[start + training_days : start + training_days + testing_days]

        opt = portfolio_optimizer(train, type_specific_weights, etf_yields, etf_expenses, top_etf_df)
        weights_df, _ = opt.run_custom_slsqp_optimization(None, key)
        w = weights_df.set_index("ETF").reindex(portfolio_returns.columns)["Weight"].values

        segment = portfolio_value * np.cumprod(1 + test.values @ w)
        path.extend(segment.tolist())
        indices.extend(test.index.tolist())
        portfolio_value = segment[-1]

        start += testing_days

    path = np.array(path)
    dd   = _drawdown(path)

    bench_path = initial_value * np.cumprod(
        1 + benchmark_returns.reindex(indices).fillna(0).values
    )
    bench_dd = _drawdown(bench_path)

    portfolio_return = path[-1]       / initial_value - 1
    benchmark_return = bench_path[-1] / initial_value - 1

    text = (
        f"Portfolio Return: {portfolio_return:.2%}\n"
        f"Benchmark Return: {benchmark_return:.2%}"
    )

    rebal_dates = [indices[i] for i in range(testing_days, len(indices), testing_days)]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    ax1.plot(indices, path,       label="Portfolio",  color="purple")
    ax1.plot(indices, bench_path, label="Benchmark",  color="blue")
    ax1.axhline(initial_value, color="black", linestyle="--", linewidth=1, label="Starting value")
    for d in rebal_dates:
        ax1.axvline(d, color="gray", alpha=0.3, linestyle="--")
    ax1.text(1.02, 0.95, text, transform=ax1.transAxes, fontsize=11,
             verticalalignment="top",
             bbox=dict(facecolor="lightblue", alpha=0.5, boxstyle="round"))
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.set_title("Performance If Re-Optimized Every Quarter")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2.plot(indices, dd,       color="purple", label="Portfolio Drawdown")
    ax2.plot(indices, bench_dd, color="blue",   label="Benchmark Drawdown")
    ax2.fill_between(indices, dd,       0, alpha=0.15, color="purple")
    ax2.fill_between(indices, bench_dd, 0, alpha=0.15, color="blue")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Drawdown")
    ax2.set_title("Drawdown")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    if show:
        plt.show()

    return path, fig

def plot_efficient_frontier(
    returns: pd.DataFrame,
    optimized_weights: np.ndarray = None,
    rf: float = 0.04,
    n_portfolios: int = 5000,
) -> None:
    lw = LedoitWolf()
    lw.fit(returns)
    cov = lw.covariance_ * 252
    mu  = returns.mean().values * 252
    n   = len(mu)

    # random portfolio cloud — colored by Sharpe
    rng      = np.random.default_rng(42)
    rw       = rng.dirichlet(np.ones(n), size=n_portfolios)
    r_vols   = np.sqrt(np.einsum("ij,jk,ik->i", rw, cov, rw)) * 100
    r_rets   = (rw @ mu) * 100
    r_sharpe = (rw @ mu - rf) / np.sqrt(np.einsum("ij,jk,ik->i", rw, cov, rw))

    # efficient frontier curve — minimize variance at each target return
    bounds     = [(0, 1)] * n
    sum1       = {"type": "eq", "fun": lambda w: w.sum() - 1}
    tgts       = np.linspace(mu.min(), mu.max(), 80)
    front_vols, front_rets = [], []
    for tgt in tgts:
        res = minimize(
            lambda w: float(w @ cov @ w),
            np.full(n, 1 / n),
            method="SLSQP",
            bounds=bounds,
            constraints=[sum1, {"type": "eq", "fun": lambda w, t=tgt: w @ mu - t}],
            options={"ftol": 1e-9},
        )
        if res.success:
            front_vols.append(np.sqrt(res.fun) * 100)
            front_rets.append(tgt * 100)

    # max Sharpe portfolio
    res_ms    = minimize(
        lambda w: -float(w @ mu - rf) / (np.sqrt(w @ cov @ w) + 1e-10),
        np.full(n, 1 / n),
        method="SLSQP", bounds=bounds, constraints=[sum1], options={"ftol": 1e-9},
    )
    ms_vol    = np.sqrt(res_ms.x @ cov @ res_ms.x) * 100
    ms_ret    = float(res_ms.x @ mu) * 100
    ms_sharpe = (res_ms.x @ mu - rf) / np.sqrt(res_ms.x @ cov @ res_ms.x)

    # min variance portfolio
    res_mv = minimize(
        lambda w: float(w @ cov @ w),
        np.full(n, 1 / n),
        method="SLSQP", bounds=bounds, constraints=[sum1], options={"ftol": 1e-9},
    )
    mv_vol = np.sqrt(res_mv.x @ cov @ res_mv.x) * 100
    mv_ret = float(res_mv.x @ mu) * 100

    # Capital Market Line through max Sharpe
    cml_vols = np.linspace(0, r_vols.max() * 0.85, 200)
    cml_rets = rf * 100 + (ms_ret - rf * 100) / ms_vol * cml_vols

    # --- plot ---
    _, ax = plt.subplots(figsize=(11, 7))

    sc   = ax.scatter(r_vols, r_rets, c=r_sharpe, cmap="viridis", alpha=0.35, s=8, zorder=1)
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("Sharpe Ratio", fontsize=11)

    if len(front_vols) > 1:
        ax.plot(front_vols, front_rets, color="white", linewidth=3.5, zorder=2)
        ax.plot(front_vols, front_rets, color="black", linewidth=2, linestyle="--",
                zorder=3, label="Efficient Frontier")

    ax.plot(cml_vols, cml_rets, color="tomato", linewidth=1.8, zorder=3,
            label="Capital Market Line")

    ax.scatter(ms_vol, ms_ret, color="gold", s=250, zorder=5, marker="*",
               edgecolors="black", linewidth=0.8,
               label=f"Max Sharpe  ({ms_sharpe:.2f})")
    ax.scatter(mv_vol, mv_ret, color="cyan",  s=150, zorder=5, marker="D",
               edgecolors="black", linewidth=0.8, label="Min Variance")

    if optimized_weights is not None:
        opt_ret    = float(optimized_weights @ mu) * 100
        opt_vol    = float(np.sqrt(optimized_weights @ cov @ optimized_weights)) * 100
        opt_sharpe = (opt_ret / 100 - rf) / (opt_vol / 100)
        ax.scatter(opt_vol, opt_ret, color="red", s=250, zorder=6, marker="*",
                   edgecolors="white", linewidth=1,
                   label=f"Your Portfolio  (Sharpe: {opt_sharpe:.2f})")

    ax.set_xlabel("Annualized Volatility (%)", fontsize=12)
    ax.set_ylabel("Annualized Return (%)",     fontsize=12)
    ax.set_title("Efficient Frontier",         fontsize=14)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=10)
    plt.tight_layout()
    plt.show()

def rate_hike_stress_test(
    returns: pd.DataFrame,
    weights: np.ndarray,
    initial_value: float,
    benchmark_returns: pd.Series,
    start: str = "2022-01-01",
    end: str = "2022-12-31",
    show: bool = True,
) -> tuple:
    stress_ret   = returns.loc[start:end]
    stress_bench = benchmark_returns.reindex(stress_ret.index).fillna(0)

    if stress_ret.empty:
        raise ValueError(f"No returns data between {start} and {end}")

    port_path  = initial_value * np.cumprod(1 + stress_ret.values @ weights)
    bench_path = initial_value * np.cumprod(1 + stress_bench.values)
    port_dd    = _drawdown(port_path)
    bench_dd   = _drawdown(bench_path)

    total_return     = port_path[-1]  / initial_value - 1
    benchmark_return = bench_path[-1] / initial_value - 1
    best_return      = port_path.max() / initial_value - 1
    worst_return     = port_path.min() / initial_value - 1
    mean_val         = float(port_path.mean())
    median_val       = float(np.median(port_path))

    text = (
        f"Total Return: {total_return:.2%}\n"
        f"Benchmark:    {benchmark_return:.2%}\n"
        f"Best:         {best_return:.2%}\n"
        f"Worst:        {worst_return:.2%}\n"
        f"Mean:       ${mean_val:,.0f}\n"
        f"Median:     ${median_val:,.0f}"
    )

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    ax1.plot(stress_ret.index, port_path,  label="Portfolio", color="purple")
    ax1.plot(stress_ret.index, bench_path, label="Benchmark", color="blue")
    ax1.axhline(initial_value, color="black",  linestyle="--", linewidth=1,   label="Starting value")
    ax1.axhline(mean_val,      color="green",  linestyle="--", linewidth=1.5, label=f"Average (${mean_val:,.0f})")
    ax1.axhline(median_val,    color="orange", linestyle="--", linewidth=1.5, label=f"Typical (${median_val:,.0f})")
    ax1.text(1.02, 0.95, text, transform=ax1.transAxes, fontsize=11,
             verticalalignment="top",
             bbox=dict(facecolor="lightblue", alpha=0.5, boxstyle="round"))
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.set_title(f"How the Portfolio Would Have Fared in the {start[:4]} Rate Hikes")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2.plot(stress_ret.index, port_dd,  color="purple", label="Portfolio Drawdown")
    ax2.plot(stress_ret.index, bench_dd, color="blue",   label="Benchmark Drawdown")
    ax2.fill_between(stress_ret.index, port_dd,  0, alpha=0.15, color="purple")
    ax2.fill_between(stress_ret.index, bench_dd, 0, alpha=0.15, color="blue")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Drawdown")
    ax2.set_title("Drawdown")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    if show:
        plt.show()

    return port_path, bench_path, fig
