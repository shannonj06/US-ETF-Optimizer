// Plain-English labels + explanations for the internal parameter/method names
// used across the optimizer form, results, graphs, and saved-portfolios pages.
// Keep the keys in sync with config/profiles.js and the backend's /optimize response.

// unit: "currency" | "percent" | "years" — drives how the field is displayed/edited
// in the optimizer form. The underlying state always stays in the raw units the
// backend expects (fractional decimal for percent, whole dollars for currency).
export const SCREENING_LABELS = {
    aum_min:      { label: "Minimum Fund Size (AUM)", hint: "ETFs smaller than this are excluded — bigger funds are generally easier to trade.", unit: "currency" },
    max_expense:  { label: "Maximum Expense Ratio", hint: "ETFs charging more than this in annual fees are excluded.", unit: "percent" },
    max_duration: { label: "Maximum Duration (years)", hint: "Caps interest-rate sensitivity for bond ETFs. Not applicable to equity ETFs.", unit: "years" },
};

export const SCORE_WEIGHT_LABELS = {
    beta:    { label: "Market Sensitivity (Beta)", hint: "How much weight is given to how closely an ETF tracks the overall market.", unit: "percent" },
    yield:   { label: "Income Yield", hint: "Favors ETFs with higher dividend or interest income.", unit: "percent" },
    sharpe:  { label: "Risk-Adjusted Return (Sharpe Ratio)", hint: "Favors ETFs with strong returns relative to their volatility.", unit: "percent" },
    aum:     { label: "Fund Size (AUM)", hint: "Favors larger, more established funds.", unit: "percent" },
    liq:     { label: "Liquidity", hint: "Favors ETFs that are easier to trade without moving the price.", unit: "percent" },
    ann_vol: { label: "Volatility", hint: "Favors more stable, lower-volatility ETFs.", unit: "percent" },
    expense: { label: "Cost (Expense Ratio)", hint: "Favors ETFs with lower fees.", unit: "percent" },
    style:   { label: "Style Fit", hint: "Favors ETFs that match the target investment style.", unit: "percent" },
};

export const OPTIMIZER_WEIGHT_LABELS = {
    sharpe:          { label: "Risk-Adjusted Return (Sharpe Ratio)", hint: "How much the optimizer prioritizes strong risk-adjusted returns.", unit: "percent" },
    yield:           { label: "Income Yield", hint: "How much the optimizer prioritizes portfolio income.", unit: "percent" },
    drawdown:        { label: "Downside Protection", hint: "How much the optimizer prioritizes limiting the worst losses.", unit: "percent" },
    diversification: { label: "Diversification", hint: "How much the optimizer prioritizes spreading risk across holdings.", unit: "percent" },
    expense:         { label: "Cost (Expense Ratio)", hint: "How much the optimizer prioritizes lower fees.", unit: "percent" },
};

// Chart keys returned under result.methods.{method}.charts / evaluate's .charts —
// keep in sync with backend/core.py's CHART_LABELS.
export const CHART_LABELS = {
    monte_carlo:         "Monte Carlo",
    monte_carlo_dist:    "Monte Carlo Distribution",
    backtest:            "Growth of $1",
    return_distribution: "Return Distribution",
    walk_forward:        "Walk Forward",
    rate_hike:           "Rate Hike Stress",
};

// Optimization methods returned by the backend under result.methods.{key}
export const METHOD_LABELS = {
    cvxpy: {
        label: "Balanced Allocation",
        hint: "A constrained optimization approach that balances your target objectives (Sharpe, yield, drawdown, diversification, cost) against hard portfolio limits.",
    },
    slsqp: {
        label: "Custom-Weighted Allocation",
        hint: "Built directly from the Optimizer Weights you set — the method most responsive to your custom priorities.",
    },
    hrp: {
        label: "Diversification-Focused Allocation",
        hint: "Groups ETFs by how similarly they move and spreads risk across those groups, rather than targeting a specific return objective.",
    },
};
