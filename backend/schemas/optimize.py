"""Request models for ``/optimize`` and ``/evaluate``.

These used to accept bare ``dict`` payloads, so a typo in a weight key was
silently ignored and an out-of-range number reached the solver as a confusing
failure hundreds of lines deep. Validation here rejects unknown keys and
out-of-range values at the edge, with a message that names the offending field.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Keys the pipeline understands. A payload may send a subset (the route fills the
# rest from the profile defaults) but never an unknown key.
SCREENING_KEYS = frozenset({"aum_min", "max_expense", "max_duration"})
SCORE_WEIGHT_KEYS = frozenset({
    "beta", "yield", "sharpe", "aum", "liq", "ann_vol", "expense", "style",
})
OPTIMIZER_WEIGHT_KEYS = frozenset({
    "sharpe", "yield", "drawdown", "diversification", "expense",
})

# Plausible bounds per screening field: (min, max, human description).
SCREENING_RANGES = {
    "aum_min":      (0.0, 1e13, "assets under management in dollars"),
    "max_expense":  (0.0, 1.0, "an expense ratio as a fraction (0.006 = 0.60%)"),
    "max_duration": (0.0, 100.0, "duration in years"),
}

# Yahoo-style ticker: letters, digits, dot and hyphen (BRK-B, BAM.TO).
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,11}$")

MAX_EVALUATE_HOLDINGS = 50


def _validate_weight_map(value: dict, allowed: frozenset[str], label: str) -> dict:
    """Shared check for the two weight dictionaries."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object of name -> number.")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(
            f"Unknown {label} key(s): {', '.join(unknown)}. "
            f"Expected any of: {', '.join(sorted(allowed))}."
        )
    cleaned: dict[str, float] = {}
    for key, raw in value.items():
        try:
            num = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{label}['{key}'] must be a number, got {raw!r}.")
        if num != num or num in (float("inf"), float("-inf")):
            raise ValueError(f"{label}['{key}'] must be a finite number.")
        if not 0.0 <= num <= 1.0:
            raise ValueError(
                f"{label}['{key}'] must be between 0 and 1 (got {num})."
            )
        cleaned[key] = num
    if cleaned and sum(cleaned.values()) <= 0:
        raise ValueError(f"{label} must not be all zero.")
    return cleaned


class OptimizeRequest(BaseModel):
    profile: str
    screening: dict = Field(default_factory=dict)
    score_weights: dict = Field(default_factory=dict)
    optimizer_weights: dict = Field(default_factory=dict)
    include_charts: bool = True
    market: str = "US"          # "US" or "CA" — which ETF universe to optimize

    @field_validator("profile", "market")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Must not be blank.")
        return v

    @field_validator("screening")
    @classmethod
    def _check_screening(cls, v: dict) -> dict:
        if not isinstance(v, dict):
            raise ValueError("screening must be an object.")
        unknown = sorted(set(v) - SCREENING_KEYS)
        if unknown:
            raise ValueError(
                f"Unknown screening key(s): {', '.join(unknown)}. "
                f"Expected any of: {', '.join(sorted(SCREENING_KEYS))}."
            )
        cleaned: dict[str, float] = {}
        for key, raw in v.items():
            try:
                num = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"screening['{key}'] must be a number, got {raw!r}.")
            lo, hi, description = SCREENING_RANGES[key]
            if num != num or not lo <= num <= hi:
                raise ValueError(
                    f"screening['{key}'] must be between {lo:g} and {hi:g} "
                    f"({description}); got {num}."
                )
            cleaned[key] = num
        return cleaned

    @field_validator("score_weights")
    @classmethod
    def _check_score_weights(cls, v: dict) -> dict:
        return _validate_weight_map(v, SCORE_WEIGHT_KEYS, "score_weights")

    @field_validator("optimizer_weights")
    @classmethod
    def _check_optimizer_weights(cls, v: dict) -> dict:
        return _validate_weight_map(v, OPTIMIZER_WEIGHT_KEYS, "optimizer_weights")


class EvaluateRequest(BaseModel):
    weights: dict[str, float]
    period: Literal["1y", "2y", "3y", "4y", "5y"] = "5y"
    rf: float = Field(default=0.04, ge=-0.5, le=1.0)

    @field_validator("weights")
    @classmethod
    def _check_weights(cls, v: dict) -> dict:
        if not v:
            raise ValueError("Enter at least one holding.")
        if len(v) > MAX_EVALUATE_HOLDINGS:
            raise ValueError(
                f"Too many holdings ({len(v)}); the maximum is {MAX_EVALUATE_HOLDINGS}."
            )
        cleaned: dict[str, float] = {}
        for raw_ticker, raw_weight in v.items():
            ticker = str(raw_ticker).strip().upper()
            if not _TICKER_RE.match(ticker):
                raise ValueError(
                    f"'{raw_ticker}' is not a valid ticker symbol."
                )
            if ticker in cleaned:
                raise ValueError(f"Duplicate ticker '{ticker}'. Enter each ETF once.")
            weight = float(raw_weight)
            if weight != weight or weight in (float("inf"), float("-inf")):
                raise ValueError(f"The weight for {ticker} must be a finite number.")
            if weight < 0:
                raise ValueError(f"The weight for {ticker} must not be negative.")
            cleaned[ticker] = weight
        if sum(cleaned.values()) <= 0:
            raise ValueError("Portfolio weights sum to zero; enter positive weights.")
        return cleaned
