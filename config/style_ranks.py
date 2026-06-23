STYLE_RANKS = {

    "conservative": {

        # Cash / ultra-safe
        "Ultra Short-Low Risk":          1,
        "Ultra Short Term Bond":         1,
        "Money Market":                  1,
        "Low Risk Bank Deposit":         1,
        "High Interest Savings Account": 1,

        # Very safe income
        "Short Term Government Bond":    2,
        "Short Term High Quality":       2,
        "Treasury Bond":                 2,

        # Moderate risk
        "Short Term Bond":               3,
        "Short Term Mid Quality":        3,
        "Multi Alternative":             3,

        # Slightly riskier
        "Short Term Low Quality":        4,
        "Short Term High Yield Bond":    4,

        # Intermediate duration
        "Intermediate Term Government Bond": 5,
        "Intermediate Term Bond":        5,
        "Intermediate Term High Quality":5,
        "Long Term Government Bond":     5,
        "Long Term Bond":                5,
        "Investment Grade Bond":         5,

        # Higher credit / duration risk
        "Intermediate Term Mid Quality": 6,
        "Long Term Mid Quality":         6,
        "Long Term High Quality":        6,

        # Riskier credit
        "Intermediate Term Low Quality": 7,
        "High Yield Bond":               8,

        # Equity-like
        "Preferred Stock":               8,

        # Risk assets
        "Real Estate":                   8,
        "Equity":                        9,
        "Commodity":                     9,
        "Cryptocurrency":               10,

        # Unknown fallback
        "Unknown":                      10,
    },


    "enhanced": {

        # Cash still acceptable but less preferred
        "Ultra Short-Low Risk":          5,
        "Ultra Short Term Bond":         5,
        "Money Market":                  5,
        "Low Risk Bank Deposit":         5,
        "High Interest Savings Account": 5,

        # Moderate safety
        "Short Term Government Bond":    4,
        "Short Term High Quality":       4,
        "Treasury Bond":                 4,

        # Balanced preference
        "Short Term Bond":               3,
        "Short Term Mid Quality":        3,
        "Multi Alternative":             4,

        # Moderate income focus
        "Short Term Low Quality":        4,
        "Short Term High Yield Bond":    4,

        # Intermediate duration acceptable
        "Intermediate Term Government Bond": 5,
        "Intermediate Term Bond":        4,
        "Intermediate Term High Quality":4,
        "Intermediate Term Mid Quality": 4,

        # Longer duration less preferred
        "Long Term Government Bond":     7,
        "Long Term Bond":                6,
        "Long Term Mid Quality":         6,
        "Long Term High Quality":        7,

        # Credit products
        "Investment Grade Bond":         5,
        "Intermediate Term Low Quality": 6,
        "High Yield Bond":               7,

        # Equity-like
        "Preferred Stock":               6,

        # Risk assets
        "Real Estate":                   7,
        "Equity":                        8,
        "Commodity":                     8,
        "Cryptocurrency":               10,

        # Unknown fallback
        "Unknown":                      10,
    },

    "strategic": {

        # Cash-like least useful
        "Ultra Short-Low Risk":          8,
        "Ultra Short Term Bond":         8,
        "Money Market":                  9,
        "Low Risk Bank Deposit":         9,
        "High Interest Savings Account": 9,

        # High quality lower preference
        "Short Term Government Bond":    7,
        "Short Term High Quality":       7,
        "Treasury Bond":                 7,

        # Higher yield preferred
        "Short Term Bond":               2,
        "Short Term Mid Quality":        2,
        "Short Term Low Quality":        2,
        "Short Term High Yield Bond":    3,

        # Intermediate acceptable
        "Intermediate Term Bond":        3,
        "Intermediate Term Mid Quality": 3,
        "Intermediate Term Low Quality": 3,

        # Higher risk acceptable
        "High Yield Bond":               2,
        "Preferred Stock":               4,
        "Multi Alternative":             2,

        # Long duration less attractive
        "Intermediate Term Government Bond": 8,
        "Intermediate Term High Quality":7,
        "Long Term Government Bond":     8,
        "Long Term Bond":                7,
        "Long Term Mid Quality":         5,
        "Long Term High Quality":        8,

        # IG okay but not ideal
        "Investment Grade Bond":         6,

        # Risk assets preferred
        "Real Estate":                   5,
        "Equity":                        4,
        "Commodity":                     6,
        "Cryptocurrency":                8,

        # Unknown fallback
        "Unknown":                      10,
    }
}