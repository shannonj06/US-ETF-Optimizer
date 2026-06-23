OPTIMIZER_CONFIG = {
    "conservative": {
        "slsqp_weights": {
            "sharpe":          0.35,
            "yield":           0.20,
            "drawdown":        0.25,
            "diversification": 0.12,
            "expense":         0.08,
        },
        "lambda":      4.0,
        "yield_floor": 0.03,
        "hhi_cap":     0.05,   # effective N >= 20 names
    },
    "enhanced": {
        "slsqp_weights": {
            "sharpe":          0.40,
            "yield":           0.25,
            "drawdown":        0.18,
            "diversification": 0.10,
            "expense":         0.07,
        },
        "lambda":      3.0,
        "yield_floor": 0.04,
        "hhi_cap":     0.0667,  # effective N >= 15 names
    },
    "strategic": {
        "slsqp_weights": {
            "sharpe":          0.30,
            "yield":           0.35,
            "drawdown":        0.15,
            "diversification": 0.12,
            "expense":         0.08,
        },
        "lambda":      0.75,
        "yield_floor": 0.05,
        "hhi_cap":     0.08,    # effective N >= ~12 names
    },
    # Black-Litterman global params — same across all profiles.
    # tau: scales uncertainty in the equilibrium prior (lower = more trust in equilibrium).
    # delta: market risk aversion used to back out implied equilibrium returns.
    "bl": {
        "tau":   0.05,
        "delta": 2.5,
    },
}
