
import pandas as pd
from scoring.score_norm_select import select_top_etfs
from config.profiles import PORTFOLIO_PROFILES 
import numpy as np
from scoring.metrics import fetch_prices 
from scoring.metrics import returns_matrix
from Optimizer_Class.optimizer2 import portfolio_optimizer, shrink_covariance
from Optimizer_Class.optimizer_weights import OPTIMIZER_CONFIG
from Optimizer_Class.get_portfolio_metrics import get_portfolio_metrics
from Optimizer_Class.hrp_optimization import hrp_allocate, hrp_core4
from models.monte_carlo import (
    monte_carlo_simulation,
    monte_carlo_metrics,
    back_testing,
    walk_forward_backtest,
    plot_efficient_frontier,
    rate_hike_stress_test,
)
from Optimizer_Class.strategy_returns import get_strategy_returns
from configuration import MONGODB_URL
from pymongo import MongoClient

client = MongoClient(MONGODB_URL)
db = client["etf_data"]
collection = db["US_ETF_DATA"]
data = list(collection.find({}, {"_id": 0}))   # exclude Mongo's _id column


def main():
    df = pd.DataFrame(data)

    #here you want to change out what profile you want to use, 
    # and then run the select_top_etfs function to get the top 30 etfs based on that profile
    top_etf_df = select_top_etfs(df, PORTFOLIO_PROFILES, 'enhanced', 40)
    print(top_etf_df[["Symbol", "score"]])

    tickers = top_etf_df["Symbol"].tolist()

   
    price_df = fetch_prices(tickers, "3y")
    print(price_df.shape)
    print(price_df.isna().sum())   # per-ticker NaN counts
    returns_df = returns_matrix(price_df).replace([np.inf, -np.inf], np.nan).dropna(axis=1)
    top_etf_df = top_etf_df[top_etf_df["Symbol"].isin(returns_df.columns)].reset_index(drop=True)
    print(returns_df.head())
    corr = returns_df.corr()
    avg_corr = (
    corr.where(~np.eye(len(corr), dtype=bool))
        .stack()
        .mean()
)
    print(avg_corr)

    print("returns shape:", returns_df.shape)
    print("returns columns:", list(returns_df.columns))
    yield_df = top_etf_df.set_index("Symbol")["YIELD"]
    expense_df = top_etf_df.set_index("Symbol")["ER"]/100

    print("RUNNING SLSQP OPTIMIZATION>>>>>>>>>>>>>>>>>>>")
    optimizer = portfolio_optimizer(returns_df, OPTIMIZER_CONFIG, yield_df, expense_df, top_etf_df)
    slsqp_weights_df, _ = optimizer.run_custom_slsqp_optimization(None, "enhanced")
    print(slsqp_weights_df)
    print(get_portfolio_metrics(slsqp_weights_df, returns_df, corr))

    print("RUNNING CVXPY OPTIMIZATION>>>>>>>>>>>>>>>>>>>>>")
    cvxpy_weights_df, _ = optimizer.run_cvxpy_optimization("enhanced")
    print(cvxpy_weights_df)
    print(get_portfolio_metrics(cvxpy_weights_df, returns_df, corr))

    print("RUNNING HRP OPTIMIZATION>>>>>>>>>>>>>>>>>>>>>")
    # HRP clusters assets, so feed it the shrunk covariance (same estimator the
    # other optimizers use). plot=True shows the cluster dendrogram.
    hrp_cov = shrink_covariance(returns_df)
    hrp_weights = hrp_allocate(hrp_cov, method="ward", plot=True)
    # reshape the Series into the ETF/Weight frame the metrics/plot helpers expect
    hrp_weights_df = (
        hrp_weights.rename("Weight")
        .rename_axis("ETF")
        .reset_index()
        .sort_values("Weight", ascending=False)
        .reset_index(drop=True)
    )
    print(hrp_weights_df)
    print(get_portfolio_metrics(hrp_weights_df, returns_df, corr))


    # aligned weight arrays for downstream analysis
    def to_weights_arr(df):
        return df.set_index("ETF")["Weight"].reindex(returns_df.columns).fillna(0).values

    slsqp_w = to_weights_arr(slsqp_weights_df)
    cvxpy_w = to_weights_arr(cvxpy_weights_df)
    hrp_w = to_weights_arr(hrp_weights_df)

    print("RUNNING FINAL OPTIMIZATION OF CVXPY, SLSQP, HRP>>>>>>>>>>")
    # meta-layer: HRP over the three strategy return streams -> one weight per STYLE
    strategy_returns = get_strategy_returns(returns_df, slsqp_w, cvxpy_w, hrp_w)
    style_cov = shrink_covariance(strategy_returns)
    style_w = hrp_allocate(style_cov, method="ward", plot=True)   # indexed 'slsqp'/'cvxpy'/'hrp'
    style_w_df = (
        style_w.rename("Weight")
        .rename_axis("Style")
        .reset_index()
        .sort_values("Weight", ascending=False)
        .reset_index(drop=True)
    )
    print(style_w_df)

    # fold the style weights back into the ASSET universe so the metrics/plots are
    # computed on real holdings:  final_w = Σ_style  λ_style · w_style
    final_w = (
        style_w["slsqp"] * slsqp_w
        + style_w["cvxpy"] * cvxpy_w
        + style_w["hrp"]  * hrp_w
    )
    final_weights_df = (
        pd.DataFrame({"ETF": returns_df.columns, "Weight": final_w})
        .sort_values("Weight", ascending=False)
        .reset_index(drop=True)
    )
    print(final_weights_df)
    print(get_portfolio_metrics(final_weights_df, returns_df, corr))

    # the HRP leg ignores the yield floor, so the blend can drift below it — check
    blended_yield = float(yield_df.reindex(returns_df.columns).fillna(0).values @ final_w)
    print(f"Blended portfolio yield: {blended_yield:.2%} (floor {optimizer.yield_floor:.2%})")
    if blended_yield < optimizer.yield_floor:
        print("  WARNING: blend fell below the yield floor — trim the HRP weight or re-project onto the floor.")


    # equal-weighted universe as benchmark
    benchmark = returns_df.mean(axis=1)

    INITIAL_VALUE = 1_000_000

    # ── CORE-4 PORTFOLIOS ──────────────────────────────────────────────────────
    # A concentrated 4-ETF sleeve per method, each still following its own optimizer:
    #   SLSQP -> enumerate every 4-ETF subset, fit the same blended-score objective
    #   CVXPY -> MIQP selects exactly 4 jointly with the weights (needs SCIP/Gurobi)
    #   HRP   -> cut the dendrogram into 4 clusters, one rep each, re-run HRP on them
    print("\nBUILDING CORE-4 PORTFOLIOS >>>>>>>>>>>>>>>>>>>>>")
    core4 = {}  # label -> weights_arr aligned to returns_df.columns

    print("\nCORE-4 SLSQP >>>>>>>>>>")
    slsqp4_df, slsqp4_metrics = optimizer.run_slsqp_core_k("enhanced", k=4)
    print(slsqp4_df)
    print("selected:", slsqp4_metrics["selected"])
    print(get_portfolio_metrics(slsqp4_df, returns_df, corr))
    core4["SLSQP-4"] = to_weights_arr(slsqp4_df)

    print("\nCORE-4 CVXPY >>>>>>>>>>")
    try:
        cvxpy4_df, cvxpy4_metrics = optimizer.run_cvxpy_cardinality("enhanced", k=4)
        print(cvxpy4_df)
        print("selected:", cvxpy4_metrics["selected"])
        print(get_portfolio_metrics(cvxpy4_df, returns_df, corr))
        core4["CVXPY-4"] = to_weights_arr(cvxpy4_df)
    except Exception as e:  # e.g. no MIQP solver installed -> keep the run going
        print(f"CVXPY core-4 skipped: {e}")

    print("\nCORE-4 HRP >>>>>>>>>>")
    hrp4_w = hrp_core4(shrink_covariance(returns_df), k=4)
    hrp4_df = hrp4_w.rename("Weight").rename_axis("ETF").reset_index()
    print(hrp4_df)
    print(get_portfolio_metrics(hrp4_df, returns_df, corr))
    core4["HRP-4"] = to_weights_arr(hrp4_df)

    # graphs per sleeve: efficient frontier, Monte Carlo metrics, backtest
    for label, w_arr in core4.items():
        print(f"\nCORE-4 GRAPHS ({label}) >>>>>>>>>>")
        plot_efficient_frontier(returns_df, optimized_weights=w_arr)
        c4_paths = monte_carlo_simulation(returns_df, w_arr, INITIAL_VALUE, years=5, simulations=1000)
        c4_metrics, _, _ = monte_carlo_metrics(c4_paths, INITIAL_VALUE)
        print(pd.DataFrame([c4_metrics]).T.rename(columns={0: "Value"}))
        back_testing(returns_df, w_arr, INITIAL_VALUE, benchmark)

    # ── 1. Efficient Frontier (one chart per portfolio for comparison) ─────────
    print("\nPLOTTING EFFICIENT FRONTIER >>>>>>>>>>>>>>>>>>>>>")
    plot_efficient_frontier(returns_df, optimized_weights=slsqp_w)
    plot_efficient_frontier(returns_df, optimized_weights=cvxpy_w)
    plot_efficient_frontier(returns_df, optimized_weights=hrp_w)

    # ── 2. Monte Carlo (5-year, 1 000 simulations, SLSQP weights) ─────────────
    print("\nRUNNING MONTE CARLO SIMULATION >>>>>>>>>>>>>>>>>>>>>")
    paths = monte_carlo_simulation(returns_df, slsqp_w, INITIAL_VALUE, years=5, simulations=1000)
    mc_metrics, _, _ = monte_carlo_metrics(paths, INITIAL_VALUE)
    print(pd.DataFrame([mc_metrics]).T.rename(columns={0: "Value"}))

    print("\nRUNNING MONTE CARLO SIMULATION (HRP) >>>>>>>>>>>>>>>>>>>>>")
    hrp_paths = monte_carlo_simulation(returns_df, hrp_w, INITIAL_VALUE, years=5, simulations=1000)
    hrp_mc_metrics, _, _ = monte_carlo_metrics(hrp_paths, INITIAL_VALUE)
    print(pd.DataFrame([hrp_mc_metrics]).T.rename(columns={0: "Value"}))

    # ── 3. Backtest on historical window ──────────────────────────────────────
    print("\nRUNNING BACKTEST >>>>>>>>>>>>>>>>>>>>>")
    back_testing(returns_df, slsqp_w, INITIAL_VALUE, benchmark)

    print("\nRUNNING BACKTEST (HRP) >>>>>>>>>>>>>>>>>>>>>")
    back_testing(returns_df, hrp_w, INITIAL_VALUE, benchmark)

    # ── 4. Walk-forward backtest (1-year train / 63-day test windows) ─────────
    # NOTE: this re-optimizes each window via OPTIMIZER_CONFIG (SLSQP), so it is
    # not run for HRP — that would require wiring HRP into walk_forward_backtest.
    print("\nRUNNING WALK-FORWARD BACKTEST >>>>>>>>>>>>>>>>>>>>>")
    walk_forward_backtest(
        returns_df, yield_df, benchmark, expense_df,
        top_etf_df, OPTIMIZER_CONFIG, "enhanced", INITIAL_VALUE,
    )

    # ── 5. Rate-hike stress test (2022; skipped if data doesn't reach back) ───
    def run_stress_test(label, weights):
        print(f"\nRUNNING RATE HIKE STRESS TEST ({label}) >>>>>>>>>>>>>>>>>>>>>")
        try:
            rate_hike_stress_test(
                returns_df, weights, INITIAL_VALUE, benchmark,
                start="2022-01-01", end="2022-12-31",
            )
        except ValueError as e:
            print(f"Stress test skipped (insufficient history): {e}")
            # fall back to the earliest full year in the sample
            start_year = returns_df.index[0].year
            end_year   = returns_df.index[-1].year
            if end_year > start_year:
                print(f"Re-running stress test on {start_year} data instead.")
                rate_hike_stress_test(
                    returns_df, weights, INITIAL_VALUE, benchmark,
                    start=f"{start_year}-01-01", end=f"{start_year}-12-31",
                )

    run_stress_test("SLSQP", slsqp_w)
    run_stress_test("HRP", hrp_w)





if __name__ == "__main__":
    main()
    


