import pandas as pd
def get_strategy_returns(returns: pd.DataFrame, w_slsqp: pd.Series, w_cvxpy: pd.Series, w_hrp: pd.Series):
    strategy_returns = pd.DataFrame({
    "slsqp": returns @ w_slsqp,
    "cvxpy": returns @ w_cvxpy,
    "hrp": returns @ w_hrp
    })
    return strategy_returns

