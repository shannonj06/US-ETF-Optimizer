import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf
from Optimizer_Class.optimizer2 import portfolio_optimizer


def _drawdown(path: np.ndarray) -> np.ndarray:
    peak = np.maximum.accumulate(path)
    return (path - peak) / (peak + 1e-10)


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
    ax1.set_title("Monte Carlo Simulation")
    ax1.grid(alpha=0.3)
    ax1.legend()

    ax2.fill_between(x, dd_p5, 0, alpha=0.2, color="red", label="Worst 5% drawdown")
    ax2.plot(dd.mean(axis=0),           color="red",     linewidth=2,   label="Expected drawdown")
    ax2.plot(dd[np.argmin(ending)],     color="darkred", linewidth=1,
             linestyle="--",                                             label="Worst case drawdown")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xlabel("Days")
    ax2.set_ylabel("Drawdown")
    ax2.set_title("Drawdown Distribution")
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
    ax3.axvline(metrics["p5_ending"],       color="red",    linewidth=2, linestyle="--", label="5th pct")
    ax3.axvline(initial_value,              color="black",  linewidth=2, linestyle="--", label="Initial")
    ax3.set_xlabel("Ending Portfolio Value ($)")
    ax3.set_ylabel("Density")
    ax3.set_title("Distribution of Ending Values")
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

    ax1.plot(portfolio_returns.index, port_path,  label="Optimized Portfolio", color="purple")
    ax1.plot(benchmark_returns.index, bench_path, label="Benchmark",           color="blue")
    ax1.axhline(initial_value, color="black", linestyle="--", linewidth=1, label="Initial")
    ax1.text(1.02, 0.95, text, transform=ax1.transAxes, fontsize=11,
             verticalalignment="top",
             bbox=dict(facecolor="lightblue", alpha=0.5, boxstyle="round"))
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.set_title("Backtest")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

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

        # match build_portfolios: use the profile's configured yield_floor rather
        # than portfolio_optimizer's 0.04 default, or every walk-forward window
        # re-optimizes against the wrong (and for CA, infeasible) floor.
        opt = portfolio_optimizer(
            train, type_specific_weights, etf_yields, etf_expenses, top_etf_df,
            yield_floor=type_specific_weights[key].get("yield_floor", 0.04),
        )
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

    ax1.plot(indices, path,       label="Optimized Portfolio", color="purple")
    ax1.plot(indices, bench_path, label="Benchmark",           color="blue")
    ax1.axhline(initial_value, color="black", linestyle="--", linewidth=1, label="Initial")
    for d in rebal_dates:
        ax1.axvline(d, color="gray", alpha=0.3, linestyle="--")
    ax1.text(1.02, 0.95, text, transform=ax1.transAxes, fontsize=11,
             verticalalignment="top",
             bbox=dict(facecolor="lightblue", alpha=0.5, boxstyle="round"))
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.set_title("Walk-Forward Backtest")
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

    ax1.plot(stress_ret.index, port_path,  label="Optimized Portfolio", color="purple")
    ax1.plot(stress_ret.index, bench_path, label="Benchmark",           color="blue")
    ax1.axhline(initial_value, color="black",  linestyle="--", linewidth=1,   label="Initial")
    ax1.axhline(mean_val,      color="green",  linestyle="--", linewidth=1.5, label=f"Mean (${mean_val:,.0f})")
    ax1.axhline(median_val,    color="orange", linestyle="--", linewidth=1.5, label=f"Median (${median_val:,.0f})")
    ax1.text(1.02, 0.95, text, transform=ax1.transAxes, fontsize=11,
             verticalalignment="top",
             bbox=dict(facecolor="lightblue", alpha=0.5, boxstyle="round"))
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.set_title(f"Rate Hike Stress Test  ({start} – {end})")
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
