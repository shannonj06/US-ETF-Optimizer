import pandas as pd
import numpy as np
from sklearn.covariance import LedoitWolf
from scipy.optimize import minimize
import cvxpy as cp

def shrink_covariance(returns: pd.DataFrame) -> pd.DataFrame:
    lw = LedoitWolf()
    #lw is an object that knows how to estimate a covariance matrix using the Ledoit-Wolf shrinkage method. We fit it to our returns data, and then extract the covariance matrix it has learned, returning it as a DataFrame with the same index and columns as the input returns.
    lw.fit(returns)
    #otherwise this returns a df with no labels
    return pd.DataFrame(lw.covariance_, index=returns.columns, columns=returns.columns)

class portfolio_optimizer:
    def __init__(self, returns: pd.DataFrame, type_specific_weights: dict, etf_yields: pd.Series, etf_expenses: pd.Series):
        self.returns = returns
        self.type_specific_weights = type_specific_weights
        self.etf_yields = etf_yields
        self.expected_return = self.returns.mean() * 252
        self.cov_matrix = shrink_covariance(self.returns) * 252
        self.max_etf_weight = .2
        self.etf_expenses = etf_expenses
        self.bounds = [(0, self.max_etf_weight)] * len(self.returns.columns)
        self.tickers = self.returns.columns

#METRIC CALCULATIONS___________________________________________________________________________________________
    def get_portfolio_sharpe(self, weights: np.ndarray) -> float:
        portfolio_return = self.expected_return @ weights
        portfolio_std = np.sqrt(weights.T @ self.cov_matrix @ weights)
        return portfolio_return / portfolio_std if portfolio_std != 0 else 0

    def get_portfolio_yield(self, weights: np.ndarray) -> float:
        return self.etf_yields @ weights

    def get_portfolio_drawdown(self, weights: np.ndarray) -> float:
        portfolio_return = self.returns @ weights
        cumulative_return = (1 + portfolio_return).cumprod()
        running_max = cumulative_return.cummax()
        drawdown = (cumulative_return - running_max) / (running_max + 1e-8)
        return abs(drawdown.min())

    def get_portfolio_diversification(self, weights: np.ndarray) -> float:
        portfolio_std = np.sqrt(weights.T @ self.cov_matrix @ weights)
        asset_stds = np.sqrt(np.diag(self.cov_matrix))
        weighted_asset_std = np.sum(weights * asset_stds)
        return weighted_asset_std / portfolio_std if portfolio_std != 0 else 0
    
    def get_portfolio_concentration(self, weights: np.ndarray) -> float:
        hhi = np.sum(weights ** 2)
        return hhi
    
    def get_portfolio_expense(self, weights: np.ndarray) -> float:
        return weights @ self.etf_expenses
    
    def get_portfolio_variance(self, weights: np.ndarray) -> float:
        return weights.T @ self.cov_matrix @ weights

#0 is terrible, 1 is excellent
#SCORING_____________________________________________________________________________________________________
    def sharpe_score(self, weights: np.ndarray) -> float:
        return np.clip(self.get_portfolio_sharpe(weights) / 2, 0, 1) #assuming max sharpe of 2 for normalization

    def yield_score(self, weights: np.ndarray) -> float:
        return np.clip(self.get_portfolio_yield(weights) / 0.1, 0, 1) #assuming max yield of 10% for normalization

    def drawdown_score(self, weights: np.ndarray) -> float:
        return np.clip(1 - self.get_portfolio_drawdown(weights) / .5, 0, 1) #assuming max drawdown of 1 for normalization

    def diversification_score(self, weights: np.ndarray) -> float:
        return np.clip(self.get_portfolio_diversification(weights), 0, 1)

    def concentration_score(self, weights: np.ndarray) -> float:
        return np.clip(1 - self.get_portfolio_concentration(weights), 0, 1)

    def expense_score(self, weights: np.ndarray) -> float:
        return np.clip(1 - self.get_portfolio_expense(weights), 0, 1)

#CONSTRAINTS___________________________________________________________________________________________________
    def yield_constraint(self, weights):
        #want the yield of the portfolio to be greater than 4%
        return self.etf_yields @ weights - 0.04

    def concentration_constraint(self, weights):
        #want the concentration of the portfolio to be less than 0.2
        return 0.2 - self.get_portfolio_concentration(weights)

#OPTIMIZATION METHODS___________________________________________________________________________________________
    def run_custom_slsqp_optimization(self, custom_weights: dict, key: str) -> pd.DataFrame:
        optimization_weights = self.type_specific_weights[key]

        def objective_function(weights):
            sharpe_score = self.sharpe_score(weights)
            yield_score = self.yield_score(weights)
            drawdown_score = self.drawdown_score(weights)
            diversification_score = self.diversification_score(weights)
            concentration_score = self.concentration_score(weights)
            expense_score = self.expense_score(weights)

#LOOK INTO POSITIVE AND NEGATIVES 
            return -(sharpe_score * optimization_weights["sharpe"] + \
                     yield_score * optimization_weights["yield"] + \
                     drawdown_score * optimization_weights["drawdown"] + \
                     diversification_score * optimization_weights["diversification"] + \
                     concentration_score * optimization_weights["concentration"] + \
                     expense_score * optimization_weights["expense"])
        constraints = [
            {"type": "eq", "fun": lambda x: np.sum(x) - 1}, #weights must sum to 1
            {"type": "ineq", "fun": self.yield_constraint}, #min portfolio yield constraint
            {"type": "ineq", "fun": self.concentration_constraint}, #max weight constraint
        ]
        n = len(self.returns.columns)
        def feasible(w): #clip into bounds and renormalize so a seed never starts out of bounds
            w = np.clip(w, 0, self.max_etf_weight)
            return w / w.sum()

        starts = [feasible(np.array([1/n] * n))] #start with equal weights
        starts += [feasible(np.random.dirichlet(np.ones(n))) for _ in range(20)] #random restarts for the non convex objective
        if custom_weights: #include the caller's portfolio as one more seed, not the only one
            starts.append(feasible(np.array([custom_weights.get(t, 0) for t in self.tickers])))

        result = None
        for x0 in starts:
            candidate = minimize(
                fun=objective_function,
                x0=x0,
                method="SLSQP",
                bounds=self.bounds,
                constraints= constraints
            )
            if result is None or candidate.fun < result.fun: #lower fun = higher score, since we negated
                result = candidate
        weights_df = pd.DataFrame({
            "ETF": self.tickers,
            "Weight": result.x
        })
        return weights_df.sort_values("Weight", ascending=False)

    def run_custom_CVXPY_optimization(self, custom_weights: dict, key: str) -> pd.DataFrame:
        optimization_weights = custom_weights[key]
        weights = cp.Variable(len(self.returns.columns))
        returns = self.expected_return @ weights
        portfolio_yield = self.etf_yields @ weights
        portfolio_variance = cp.quad_form(weights, self.cov_matrix.values)
        concentration = cp.sum_squares(weights)
        expense = self.etf_expenses @ weights
        score = (
            optimization_weights["return"] * returns
            + optimization_weights["yield"] * portfolio_yield
            - optimization_weights["risk"] * portfolio_variance
            - optimization_weights["concentration"] * concentration
            - optimization_weights["expense"] * expense )
        constraints = [
            cp.sum(weights) == 1,
            weights >= 0,
            weights <= self.max_etf_weight,
            portfolio_yield >= 0.04,
            concentration <= 0.2
        ]
        problem = cp.Problem(cp.Maximize(score), constraints)
        problem.solve(solver=cp.SCS, verbose=False)
        if problem.status not in ["optimal", "optimal_inaccurate"]:
            raise ValueError("Optimization failed: " + problem.status)
        
        optimal_weights = weights.value
        weights_df = pd.DataFrame({
            "ETF": self.tickers,
            "Weight": optimal_weights
        })
        return weights_df.sort_values("Weight", ascending=False)