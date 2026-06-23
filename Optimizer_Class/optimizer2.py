import pandas as pd
import numpy as np
from sklearn.covariance import LedoitWolf
from scipy.optimize import minimize
import cvxpy as cp


def shrink_covariance(returns: pd.DataFrame) -> pd.DataFrame:
    lw = LedoitWolf()
    # lw estimates a covariance matrix via Ledoit-Wolf shrinkage. Fit on returns,
    # then wrap the learned covariance back into a labelled DataFrame.
    lw.fit(returns)
    return pd.DataFrame(lw.covariance_, index=returns.columns, columns=returns.columns)


class portfolio_optimizer:
    def __init__(self, returns: pd.DataFrame, config: dict,
                 etf_yields: pd.Series, etf_expenses: pd.Series,
                 top_etf_df: pd.DataFrame,
                 risk_free_rate: float = 0.04, seed: int = 42,
                 yield_floor: float = 0.04, max_etf_weight: float = 0.20):
        self.returns = returns
        self.tickers = returns.columns
        self.config = config
        self.top_etf_df = top_etf_df
        self.yield_floor = yield_floor

        self.max_etf_weight = max_etf_weight
        min_assets = int(np.ceil(1 / self.max_etf_weight))  # = 5 names at a 0.2 cap
        if len(self.tickers) < min_assets:
            raise ValueError(
                f"Need at least {min_assets} ETFs to build a portfolio at the "
                f"{self.max_etf_weight:.0%} per-asset cap, but `returns` has only "
                f"{len(self.tickers)} column(s): {list(self.tickers)}. "
                "Check how `returns` is constructed upstream (e.g. a dropna(axis=1) "
                "that collapsed columns, or a single-ticker download)."
            )

        # Align yields/expenses to the return columns and store as numpy arrays.
        # Series @ ndarray is POSITIONAL, not label-aligned, so if these came in
        # a different order than returns.columns every dot product would be silently
        # wrong. Reindexing makes position == label.
        yields = etf_yields.reindex(self.tickers)
        expenses = etf_expenses.reindex(self.tickers)
        if yields.isna().any() or expenses.isna().any():
            raise ValueError("etf_yields / etf_expenses are missing tickers present in returns")
        self.etf_yields = yields.values
        self.etf_expenses = expenses.values

        self.expected_return = (self.returns.mean() * 252).values
        cov = shrink_covariance(self.returns) * 252
        self.cov_matrix = (cov.values + cov.values.T) / 2  # force exact symmetry for CVXPY PSD check
        self.rf = risk_free_rate

        self.bounds = [(0, self.max_etf_weight)] * len(self.tickers)
        self.rng = np.random.default_rng(seed)
        # per-profile HHI cap; run methods override this from config["<profile>"]["hhi_cap"]
        self.hhi_cap = 0.2

# METRIC CALCULATIONS___________________________________________________________________________________________
    def get_portfolio_sharpe(self, weights: np.ndarray) -> float:
        excess_return = self.expected_return @ weights - self.rf  # net of risk-free rate
        portfolio_std = np.sqrt(weights.T @ self.cov_matrix @ weights)
        return excess_return / portfolio_std if portfolio_std != 0 else 0

    def get_portfolio_yield(self, weights: np.ndarray) -> float:
        return self.etf_yields @ weights

    def get_portfolio_drawdown(self, weights: np.ndarray) -> float:
        # assumes daily rebalancing back to `weights`
        portfolio_return = self.returns.values @ weights
        cumulative_return = (1 + portfolio_return).cumprod()
        running_max = np.maximum.accumulate(cumulative_return)
        drawdown = (cumulative_return - running_max) / (running_max + 1e-8)
        return abs(drawdown.min())

    def get_portfolio_diversification(self, weights: np.ndarray) -> float:
        portfolio_std = np.sqrt(weights.T @ self.cov_matrix @ weights)
        asset_stds = np.sqrt(np.diag(self.cov_matrix))
        weighted_asset_std = np.sum(weights * asset_stds)
        return weighted_asset_std / portfolio_std if portfolio_std != 0 else 0

    def get_portfolio_concentration(self, weights: np.ndarray) -> float:
        return np.sum(weights ** 2)  # HHI

    def get_portfolio_expense(self, weights: np.ndarray) -> float:
        return weights @ self.etf_expenses

    def get_portfolio_variance(self, weights: np.ndarray) -> float:
        return weights.T @ self.cov_matrix @ weights

# SCORING_______________________________________________________________________________________________________
# 0 is terrible, 1 is excellent
    def sharpe_score(self, weights: np.ndarray) -> float:
        return np.clip(self.get_portfolio_sharpe(weights) / 2, 0, 1)  # assumes Sharpe of 2 is "great"

    def yield_score(self, weights: np.ndarray) -> float:
        return np.clip(self.get_portfolio_yield(weights) / 0.1, 0, 1)  # 10% yield -> full score

    def drawdown_score(self, weights: np.ndarray) -> float:
        return np.clip(1 - self.get_portfolio_drawdown(weights) / 0.5, 0, 1)  # 50% drawdown -> score 0

    def diversification_score(self, weights: np.ndarray) -> float:
        # diversification ratio is always >= 1 and tops out near sqrt(n); the old
        # clip(.,0,1) collapsed it to a constant 1.0. Map [1, sqrt(n)] -> [0, 1].
        dr = self.get_portfolio_diversification(weights)
        n = len(weights)
        return np.clip((dr - 1) / (np.sqrt(n) - 1), 0, 1)

    def expense_score(self, weights: np.ndarray) -> float:
        # expense ratios are ~0.0003-0.01, so 1 - expense barely moves; scale against
        # a 1% worst case so the score spans the realistic range.
        return np.clip(1 - self.get_portfolio_expense(weights) / 0.01, 0, 1)

# CONSTRAINTS___________________________________________________________________________________________________
    def yield_constraint(self, weights):
        return self.etf_yields @ weights - self.yield_floor

    def concentration_constraint(self, weights):
        return self.hhi_cap - self.get_portfolio_concentration(weights)  # HHI <= cap

    def is_feasible(self, weights, tol=1e-4):
        # check the actual constraints on a candidate, rather than trusting SLSQP's
        # success flag (which it often sets False on non-smooth objectives even when
        # the returned point is perfectly fine).
        w = np.asarray(weights)
        if np.any(w < -tol) or np.any(w > self.max_etf_weight + tol):
            return False
        if abs(w.sum() - 1) > 1e-3:
            return False
        if self.get_portfolio_yield(w) < self.yield_floor - tol:
            return False
        if self.get_portfolio_concentration(w) > self.hhi_cap + tol:
            return False
        return True

    def _infeasibility_message(self) -> str:
        n = len(self.tickers)
        k = int(np.ceil(1 / self.max_etf_weight))  # min names to reach 100% at the cap (=5 at 0.2)
        max_yield = self.max_etf_weight * np.sort(self.etf_yields)[::-1][:k].sum()
        return (
            "No feasible portfolio found. Diagnostics:\n"
            f"  - universe size: {n} ETFs (need >= {k} to reach 100% at the "
            f"{self.max_etf_weight:.0%} cap -> {'OK' if n >= k else 'TOO FEW'})\n"
            f"  - best reachable yield under the weight cap: {max_yield:.2%} "
            f"(need >= {self.yield_floor:.2%} -> {'OK' if max_yield >= self.yield_floor else 'UNREACHABLE'}; "
            f"the HHI cap tightens this further)\n"
            f"  - HHI cap: {self.hhi_cap:.3f} -> forces >= {int(np.ceil(1 / self.hhi_cap))} effective names "
            f"({'OK' if n >= 1 / self.hhi_cap else 'TOO FEW IN UNIVERSE'})\n"
            f"  - fixes: lower the yield floor, raise max_etf_weight, "
            f"loosen the HHI<={self.hhi_cap:.3f} cap, or add higher-yielding ETFs."
        )

# OPTIMIZATION METHODS__________________________________________________________________________________________
    def run_custom_slsqp_optimization(self, custom_weights: dict, key: str):
        optimization_weights = self.config[key]["slsqp_weights"]
        if abs(sum(optimization_weights.values()) - 1) > 1e-6:
            raise ValueError(f"profile '{key}' slsqp_weights do not sum to 1")
        self.hhi_cap = self.config[key].get("hhi_cap", 0.2)

        def objective_function(weights):
            # negate because minimize() minimizes; higher blended score = lower fun
            # concentration is absent — enforced as a hard constraint below
            return -(
                self.sharpe_score(weights)          * optimization_weights["sharpe"] +
                self.yield_score(weights)           * optimization_weights["yield"] +
                self.drawdown_score(weights)        * optimization_weights["drawdown"] +
                self.diversification_score(weights) * optimization_weights["diversification"] +
                self.expense_score(weights)         * optimization_weights["expense"]
            )

        constraints = [
            {"type": "eq",   "fun": lambda x: np.sum(x) - 1},   # weights sum to 1
            {"type": "ineq", "fun": self.yield_constraint},     # min portfolio yield
            {"type": "ineq", "fun": self.concentration_constraint},  # max HHI
        ]

        n = len(self.tickers)

        def feasible(w):  # clip into bounds and renormalize so seeds start sane
            w = np.clip(w, 0, self.max_etf_weight)
            total = w.sum()
            if total == 0:  # e.g. custom_weights didn't overlap any ticker
                return np.full(n, 1 / n)
            return w / total

        starts = [feasible(np.full(n, 1 / n))]                                  # equal weight
        starts += [feasible(self.rng.dirichlet(np.ones(n))) for _ in range(20)]  # random restarts
        if custom_weights:  # caller's portfolio as one more seed, not the only one
            starts.append(feasible(np.array([custom_weights.get(t, 0) for t in self.tickers])))

        result = None
        for x0 in starts:
            candidate = minimize(
                fun=objective_function,
                x0=x0,
                method="SLSQP",
                bounds=self.bounds,
                constraints=constraints,
            )
            # accept on real feasibility, not candidate.success (see is_feasible note)
            if not self.is_feasible(candidate.x):
                continue
            if result is None or candidate.fun < result.fun:
                result = candidate

        if result is None:
            raise RuntimeError(self._infeasibility_message())

        weights = result.x
        weights[weights < 0.005] = 0
        weights /= weights.sum()
        weights_df = (
            pd.DataFrame({"ETF": self.tickers, "Weight": weights})
            .sort_values("Weight", ascending=False)
            .reset_index(drop=True)
        )

        # realized metrics so the caller can see what they actually got
        metrics = {
            "sharpe":          self.get_portfolio_sharpe(weights),
            "yield":           self.get_portfolio_yield(weights),
            "max_drawdown":    self.get_portfolio_drawdown(weights),
            "diversification": self.get_portfolio_diversification(weights),
            "hhi":             self.get_portfolio_concentration(weights),
            "expense":         self.get_portfolio_expense(weights),
        }
        return weights_df, metrics

    def run_slsqp_core_k(self, profile: str, k: int = 4,
                         w_min: float = 0.05, max_etf_weight: float = 0.40,
                         n_starts: int = 1):
       
        from itertools import combinations

        n = len(self.tickers)
        if n < k:
            raise ValueError(f"universe has {n} ETFs, need >= k={k}")
        if max_etf_weight < 1 / k:
            raise ValueError(f"k={k} names need max_etf_weight >= {1/k:.2f}")
        if w_min * k > 1:
            raise ValueError(f"w_min={w_min} infeasible: {k} names exceed 100%")

        opt_w = self.config[profile]["slsqp_weights"]
        if abs(sum(opt_w.values()) - 1) > 1e-6:
            raise ValueError(f"profile '{profile}' slsqp_weights do not sum to 1")

        # precompute full-universe arrays ONCE; per-subset work is just slicing
        mu_full  = self.expected_return     # annualized mean
        cov_full = self.cov_matrix          # shrunk, annualized
        ret_full = self.returns.values      # daily, for the drawdown term
        yld_full = self.etf_yields
        exp_full = self.etf_expenses

        def subset_objective(w, idx):
            # identical score formulas to the full-universe SLSQP, on the k-subset
            cov = cov_full[np.ix_(idx, idx)]
            std = np.sqrt(w @ cov @ w)

            sharpe   = (mu_full[idx] @ w - self.rf) / std if std > 0 else 0.0
            sharpe_s = np.clip(sharpe / 2, 0, 1)
            yield_s  = np.clip((yld_full[idx] @ w) / 0.1, 0, 1)

            port = ret_full[:, idx] @ w
            cum  = np.cumprod(1 + port)
            rmax = np.maximum.accumulate(cum)
            dd   = abs(((cum - rmax) / (rmax + 1e-8)).min())
            dd_s = np.clip(1 - dd / 0.5, 0, 1)

            asset_std = np.sqrt(np.diag(cov))
            dr    = (np.sum(w * asset_std) / std) if std > 0 else 1.0
            div_s = np.clip((dr - 1) / (np.sqrt(k) - 1), 0, 1)

            exp_s = np.clip(1 - (exp_full[idx] @ w) / 0.01, 0, 1)

            return -(sharpe_s * opt_w["sharpe"] +
                     yield_s  * opt_w["yield"] +
                     dd_s     * opt_w["drawdown"] +
                     div_s    * opt_w["diversification"] +
                     exp_s    * opt_w["expense"])

        bounds = [(w_min, max_etf_weight)] * k
        budget = 1 - w_min * k  # head-room above the per-name floor

        def max_subset_yield(y):
            # exact max of yᵀw s.t. sum w=1, w∈[w_min,cap]: fill highest-y names to cap
            w, rem = np.full(k, w_min), budget
            for j in np.argsort(y)[::-1]:
                add = min(max_etf_weight - w_min, rem)
                w[j] += add
                rem -= add
                if rem <= 1e-12:
                    break
            return y @ w

        starts  = [np.full(k, 1 / k)]
        starts += [self.rng.dirichlet(np.ones(k)) for _ in range(max(0, n_starts - 1))]

        best_combo, best_w, best_obj, skipped = None, None, np.inf, 0
        for combo in combinations(range(n), k):
            idx = list(combo)
            # cheap prune: skip subsets that can't even reach the yield floor
            if max_subset_yield(yld_full[idx]) < self.yield_floor - 1e-9:
                skipped += 1
                continue
            cons = [
                {"type": "eq",   "fun": lambda w: np.sum(w) - 1},
                {"type": "ineq", "fun": lambda w, i=idx: yld_full[i] @ w - self.yield_floor},
            ]
            for x0 in starts:
                res = minimize(subset_objective, x0, args=(idx,), method="SLSQP",
                               bounds=bounds, constraints=cons)
                w = res.x
                if (abs(w.sum() - 1) > 1e-3 or np.any(w < -1e-4)
                        or yld_full[idx] @ w < self.yield_floor - 1e-4):
                    continue
                if res.fun < best_obj:
                    best_obj, best_combo, best_w = res.fun, idx, w.copy()

        if best_combo is None:
            raise RuntimeError(
                f"No feasible {k}-ETF subset cleared the {self.yield_floor:.2%} yield "
                f"floor ({skipped} subsets pruned). Lower yield_floor or raise k."
            )

        w = best_w
        w[w < 0.005] = 0
        w /= w.sum()
        names = [self.tickers[i] for i in best_combo]
        weights_df = (
            pd.DataFrame({"ETF": names, "Weight": w})
            .sort_values("Weight", ascending=False)
            .reset_index(drop=True)
        )
        cov = cov_full[np.ix_(best_combo, best_combo)]
        std = float(np.sqrt(w @ cov @ w))
        metrics = {
            "selected": names,
            "sharpe":   float((mu_full[best_combo] @ w - self.rf) / std) if std > 0 else 0.0,
            "yield":    float(yld_full[best_combo] @ w),
            "expense":  float(exp_full[best_combo] @ w),
            "hhi":      float(np.sum(w ** 2)),
        }
        return weights_df, metrics

    def run_cvxpy_optimization(self, profile: str):
        # Mean-variance QP: minimize  -μᵀw + λ · wᵀΣw
        # profile: "conservative" | "enhanced" | "strategic" — resolves λ from CVXPY_PARAMS.
        # Expected returns come from Black-Litterman (score-based views + AUM equilibrium).
        from Optimizer_Class.black_litterman import black_litterman_returns
        lam = self.config[profile]["lambda"]
        self.hhi_cap = self.config[profile].get("hhi_cap", 0.2)
        mu_bl = black_litterman_returns(self.returns, self.top_etf_df)
        mu = mu_bl.reindex(self.tickers).values
        if np.isnan(mu).any():
            missing = [t for t, m in zip(self.tickers, mu) if np.isnan(m)]
            raise ValueError(f"Black-Litterman returned no expected return for: {missing}")
        n = len(self.tickers)
        w = cp.Variable(n)

        # `lambda` in config is a unitless risk-aversion dial (~0.75-4, equity-scale
        # convention). Raw wᵀΣw for ultra-short bond ETFs is ~1e-4 while μ spread is
        # ~1e-2, so unscaled the QP degenerates into an LP and pins the weight cap on
        # the top-μ names. Rescale so risk and return terms are commensurate.
        mu_spread = np.std(mu)
        median_var = np.median(np.diag(self.cov_matrix))
        lam_eff = lam * mu_spread / median_var if mu_spread > 0 and median_var > 0 else lam

        objective = cp.Minimize(
            -mu @ w + lam_eff * cp.quad_form(w, self.cov_matrix)
        )
        constraints = [
            cp.sum(w) == 1,
            w >= 0,
            w <= self.max_etf_weight,
            self.etf_yields @ w >= self.yield_floor,
            cp.sum(cp.square(w)) <= self.hhi_cap,
        ]

        prob = cp.Problem(objective, constraints)
        prob.solve(solver=cp.CLARABEL, verbose=False)

        if prob.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise RuntimeError(
                f"CVXPY solver failed: status='{prob.status}'.\n"
                + self._infeasibility_message()
            )

        weights = np.array(w.value).clip(0)
        weights[weights < 0.005] = 0
        weights /= weights.sum()

        weights_df = (
            pd.DataFrame({"ETF": self.tickers, "Weight": weights})
            .sort_values("Weight", ascending=False)
            .reset_index(drop=True)
        )
        metrics = {
            "sharpe":          self.get_portfolio_sharpe(weights),
            "yield":           self.get_portfolio_yield(weights),
            "max_drawdown":    self.get_portfolio_drawdown(weights),
            "diversification": self.get_portfolio_diversification(weights),
            "hhi":             self.get_portfolio_concentration(weights),
            "expense":         self.get_portfolio_expense(weights),
        }
        return weights_df, metrics

    @staticmethod
    def _first_available_miqp_solver():
        # CLARABEL/GLPK_MI can't do integer + quadratic. Prefer a real MIQP solver;
        # fall back to ECOS_BB (ships with CVXPY but fragile/slow on MIQP).
        available = set(cp.installed_solvers())
        for s in ("SCIP", "GUROBI", "MOSEK", "CPLEX"):
            if s in available:
                return getattr(cp, s)
        if "ECOS_BB" in available:
            return cp.ECOS_BB
        raise RuntimeError(
            "No mixed-integer solver available for the CVXPY core-k model. "
            "Install one, e.g. `pip install pyscipopt` (SCIP) or Gurobi/Mosek. "
            "(The SLSQP and HRP core-4 methods need no extra solver.)"
        )

    def run_cvxpy_cardinality(self, profile: str, k: int = 4,
                              w_min: float = 0.05, max_etf_weight: float = 0.40,
                              solver=None):
        """Same QP as run_cvxpy_optimization, plus a binary layer that selects
        EXACTLY k names — the optimizer chooses which k jointly with the weights.
        Needs an MIQP solver (SCIP/Gurobi/Mosek); GLPK_MI/CLARABEL won't work."""
        from Optimizer_Class.black_litterman import black_litterman_returns
        if max_etf_weight < 1 / k:
            raise ValueError(f"k={k} names need max_etf_weight >= {1/k:.2f}")

        lam = self.config[profile]["lambda"]
        mu  = black_litterman_returns(self.returns, self.top_etf_df).reindex(self.tickers).values
        if np.isnan(mu).any():
            missing = [t for t, m in zip(self.tickers, mu) if np.isnan(m)]
            raise ValueError(f"Black-Litterman returned no expected return for: {missing}")
        n = len(self.tickers)

        # identical lambda rescaling as run_cvxpy_optimization
        mu_spread, median_var = np.std(mu), np.median(np.diag(self.cov_matrix))
        lam_eff = lam * mu_spread / median_var if mu_spread > 0 and median_var > 0 else lam

        w = cp.Variable(n, nonneg=True)
        z = cp.Variable(n, boolean=True)            # 1 if the ETF is held

        objective = cp.Minimize(-mu @ w + lam_eff * cp.quad_form(w, self.cov_matrix))
        constraints = [
            cp.sum(w) == 1,
            cp.sum(z) == k,                          # exactly k holdings
            w <= max_etf_weight * z,                 # held-only + per-name cap (>= 1/k)
            w >= w_min * z,                          # no token weights
            self.etf_yields @ w >= self.yield_floor, # same yield floor as the full run
        ]
        prob = cp.Problem(objective, constraints)
        prob.solve(solver=solver or self._first_available_miqp_solver())

        if prob.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise RuntimeError(
                f"CVXPY cardinality solve failed: status='{prob.status}'.\n"
                + self._infeasibility_message()
            )

        weights = np.array(w.value).clip(0)
        weights[weights < 0.005] = 0
        weights /= weights.sum()

        # keep only the selected names for a clean k-row frame
        mask = weights > 0
        weights_df = (
            pd.DataFrame({"ETF": self.tickers[mask], "Weight": weights[mask]})
            .sort_values("Weight", ascending=False)
            .reset_index(drop=True)
        )
        metrics = {
            "selected":        weights_df["ETF"].tolist(),
            "sharpe":          self.get_portfolio_sharpe(weights),
            "yield":           self.get_portfolio_yield(weights),
            "max_drawdown":    self.get_portfolio_drawdown(weights),
            "diversification": self.get_portfolio_diversification(weights),
            "hhi":             self.get_portfolio_concentration(weights),
            "expense":         self.get_portfolio_expense(weights),
        }
        return weights_df, metrics
