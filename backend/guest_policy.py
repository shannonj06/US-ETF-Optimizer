"""What a signed-out ("guest") caller is allowed to do.

A guest can try the product without creating an account, but not run it as a
free service: the expensive endpoints are metered per guest and the tunable
inputs are locked to their profile defaults.

Allowance per guest (see ``GUEST_QUOTAS``):

  * 1 optimizer run  — "develop a portfolio", with restricted inputs
  * 1 evaluation     — "input your portfolio"
  * 1 cash analysis

which is two portfolios in total plus one analysis.

Enforcement lives on the server because the client-side copy of these rules
(``src/config/guestPolicy.js``) is only there to keep the UI honest — anyone can
call the API directly. Keep the two files in sync when changing a limit.
"""

from __future__ import annotations

from datetime import date, timedelta

# action -> how many times one guest may perform it.
GUEST_QUOTAS: dict[str, int] = {
    "optimize": 1,
    "evaluate": 1,
    "cash_analysis": 1,
}

# Total portfolios a guest can produce (an optimizer run plus an evaluation).
GUEST_MAX_PORTFOLIOS = GUEST_QUOTAS["optimize"] + GUEST_QUOTAS["evaluate"]

# ── Input restrictions ───────────────────────────────────────────────────────
# Guests optimize the US universe only; Canada is a signed-in feature.
GUEST_ALLOWED_MARKETS = frozenset({"US"})

# Guests may pick a style but not hand-tune the screening thresholds, scoring
# weights or optimizer objective weights — those are forced to profile defaults.
GUEST_ALLOWED_PROFILES = frozenset({"conservative", "enhanced", "strategic"})
GUEST_LOCKS_ADVANCED_INPUTS = True

# Ceilings on the free-form endpoints.
GUEST_MAX_HOLDINGS = 5                 # tickers per evaluation / cash analysis
GUEST_MAX_INITIAL_CASH = 100_000.0     # cash analysis starting amount
GUEST_MAX_HISTORY_YEARS = 5            # how far back a guest may look
GUEST_ALLOWED_PERIODS = frozenset({"1y", "2y", "3y", "4y", "5y"})
GUEST_RF_RANGE = (0.0, 0.10)           # risk-free rate bounds

# Message shown when a quota is used up, per action.
_QUOTA_MESSAGES = {
    "optimize": (
        "Guest preview: you've used your {limit} portfolio optimization. "
        "Create a free account to run more, tune the screening and optimizer "
        "inputs, and save your results."
    ),
    "evaluate": (
        "Guest preview: you've used your {limit} portfolio evaluation. "
        "Create a free account to evaluate more portfolios and save them."
    ),
    "cash_analysis": (
        "Guest preview: you've used your {limit} cash analysis. "
        "Create a free account to run more."
    ),
}


class GuestLimitExceeded(Exception):
    """A guest asked for more than their allowance of an action."""

    def __init__(self, action: str, limit: int, used: int):
        self.action = action
        self.limit = limit
        self.used = used
        template = _QUOTA_MESSAGES.get(
            action, "Guest preview: you've reached the limit for this action."
        )
        super().__init__(template.format(limit=limit))


class GuestInputNotAllowed(ValueError):
    """A guest sent an input outside the restricted guest range."""


def quota_for(action: str) -> int | None:
    """How many times a guest may perform ``action`` (None = unmetered)."""
    return GUEST_QUOTAS.get(action)


def describe() -> dict:
    """The guest allowance, for the client to render without hard-coding it."""
    return {
        "quotas": dict(GUEST_QUOTAS),
        "max_portfolios": GUEST_MAX_PORTFOLIOS,
        "allowed_markets": sorted(GUEST_ALLOWED_MARKETS),
        "allowed_profiles": sorted(GUEST_ALLOWED_PROFILES),
        "locks_advanced_inputs": GUEST_LOCKS_ADVANCED_INPUTS,
        "max_holdings": GUEST_MAX_HOLDINGS,
        "max_initial_cash": GUEST_MAX_INITIAL_CASH,
        "max_history_years": GUEST_MAX_HISTORY_YEARS,
        "allowed_periods": sorted(GUEST_ALLOWED_PERIODS),
        "rf_range": list(GUEST_RF_RANGE),
    }


# ── Per-endpoint input checks ────────────────────────────────────────────────
def check_optimize(profile: str, market: str) -> None:
    """Validate the parts of an /optimize request a guest is allowed to choose.

    The remaining inputs (screening thresholds, score weights, optimizer
    weights) are not validated here — the route replaces them wholesale with the
    profile defaults, so whatever the client sent is discarded.
    """
    if profile not in GUEST_ALLOWED_PROFILES:
        raise GuestInputNotAllowed(
            f"Guests can choose {', '.join(sorted(GUEST_ALLOWED_PROFILES))}. "
            "Create a free account for custom profiles."
        )
    if market not in GUEST_ALLOWED_MARKETS:
        raise GuestInputNotAllowed(
            "The guest preview covers the US ETF universe. "
            "Create a free account to optimize the Canadian universe."
        )


def check_evaluate(weights: dict, period: str, rf: float) -> None:
    """Validate an /evaluate request from a guest."""
    if len(weights) > GUEST_MAX_HOLDINGS:
        raise GuestInputNotAllowed(
            f"Guests can evaluate up to {GUEST_MAX_HOLDINGS} holdings "
            f"(you sent {len(weights)}). Create a free account for larger portfolios."
        )
    if period not in GUEST_ALLOWED_PERIODS:
        raise GuestInputNotAllowed(
            f"Guests can use a history window of up to {GUEST_MAX_HISTORY_YEARS} years."
        )
    lo, hi = GUEST_RF_RANGE
    if not (lo <= rf <= hi):
        raise GuestInputNotAllowed(
            f"The risk-free rate must be between {lo} and {hi} in the guest preview."
        )


def check_cash_analysis(holdings_count: int, initial_cash: float,
                        start: date, today: date | None = None) -> None:
    """Validate a /api/cash-analysis request from a guest."""
    if holdings_count > GUEST_MAX_HOLDINGS:
        raise GuestInputNotAllowed(
            f"Guests can analyze up to {GUEST_MAX_HOLDINGS} holdings "
            f"(you sent {holdings_count}). Create a free account for larger portfolios."
        )
    if initial_cash > GUEST_MAX_INITIAL_CASH:
        raise GuestInputNotAllowed(
            f"Guests can analyze up to ${GUEST_MAX_INITIAL_CASH:,.0f} of initial cash."
        )
    today = today or date.today()
    earliest = today - timedelta(days=365 * GUEST_MAX_HISTORY_YEARS)
    if start < earliest:
        raise GuestInputNotAllowed(
            f"Guests can look back up to {GUEST_MAX_HISTORY_YEARS} years "
            f"(on or after {earliest.isoformat()}). "
            "Create a free account for the full history."
        )
