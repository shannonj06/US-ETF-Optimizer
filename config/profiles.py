
PORTFOLIO_PROFILES = {

    "conservative": {

        # --- per-name screening gates ---
        "aum_min":      200_000_000,    # $200M floor — tradability / survivorship
        "max_expense":  0.0060,         # 0.60% cost ceiling
        "max_duration": 6.0,            # fund-level duration cap, years

        # --- scoring weights ---
        "score_weights": {
            "beta":     0.15,
            "yield":    0.18,
            "sharpe":   0.18,
            "aum":      0.12,
            "liq":      0.05,
            "ann_vol":  0.12,
            "expense":  0.10,
            "style":    0.10,
        },
    },

    "enhanced": {

        # --- per-name screening gates ---
        "aum_min":      500_000_000,
        "max_expense":  0.0085,         # 0.85% cost ceiling
        "max_duration": 8.0,

        # --- scoring weights ---
        "score_weights": {
            "beta":     0.08,
            "yield":    0.24,
            "sharpe":   0.22,
            "aum":      0.10,
            "liq":      0.05,
            "ann_vol":  0.08,
            "expense":  0.08,
            "style":    0.15,
        },
    },

    "strategic": {

        # --- per-name screening gates ---
        "aum_min":      250_000_000,
        "max_expense":  0.0125,         # 1.25% cost ceiling
        "max_duration": 10.0,

        # --- scoring weights ---
        "score_weights": {
            "beta":     0.05,
            "yield":    0.28,
            "sharpe":   0.22,
            "aum":      0.08,
            "liq":      0.05,
            "ann_vol":  0.08,
            "expense":  0.07,
            "style":    0.17,
        },
    },
}