"""Pydantic request/response models for ``POST /cash-analysis``.

Money values in the RESPONSE are plain floats already rounded to presentation
precision by the service (the service does the money math in ``Decimal`` and only
rounds at this boundary). The REQUEST is validated strictly here so the service
can assume clean inputs.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Request ──────────────────────────────────────────────────────────────────
class PortfolioHolding(BaseModel):
    ticker: str = Field(..., description="ETF ticker symbol")
    weight: float = Field(..., description="Target portfolio weight (fraction or %)")

    @field_validator("ticker")
    @classmethod
    def _clean_ticker(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not v:
            raise ValueError("Ticker must not be blank.")
        return v

    @field_validator("weight")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Portfolio weights must not be negative.")
        return v


class CashAnalysisRequest(BaseModel):
    portfolio: list[PortfolioHolding] = Field(..., min_length=1)
    initial_cash: float = Field(..., gt=0, description="Positive cash amount to invest")
    requested_start_date: date
    end_date: Optional[date] = Field(
        default=None,
        description="Optional analysis end; defaults to the latest available market date.",
    )
    allow_fractional_shares: bool = True
    dividend_treatment: Literal["cash", "reinvest"] = "cash"
    frequency: Literal["daily", "weekly", "monthly"] = "monthly"

    @field_validator("portfolio")
    @classmethod
    def _unique_tickers(cls, v: list[PortfolioHolding]) -> list[PortfolioHolding]:
        seen: set[str] = set()
        for h in v:
            if h.ticker in seen:
                raise ValueError(f"Duplicate ticker '{h.ticker}'. Enter each ETF once.")
            seen.add(h.ticker)
        total = sum(h.weight for h in v)
        if total <= 0:
            raise ValueError("Portfolio weights sum to zero; enter positive weights.")
        return v

    @model_validator(mode="after")
    def _date_sanity(self) -> "CashAnalysisRequest":
        today = date.today()
        if self.requested_start_date > today:
            raise ValueError("The start date must not be in the future.")
        if self.end_date is not None:
            if self.end_date > today:
                raise ValueError("The end date must not be in the future.")
            if self.requested_start_date >= self.end_date:
                raise ValueError("The start date must be before the analysis end date.")
        return self


# ── Response ─────────────────────────────────────────────────────────────────
# Response sub-models are intentionally permissive containers: the service builds
# each row as a fully-formed, JSON-safe dict and FastAPI validates it here.
class Warning(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


class ExecutionInfo(BaseModel):
    requested_start_date: str
    actual_execution_date: str
    date_adjusted: bool
    adjustment_reason: Optional[str] = None
    requested_end_date: Optional[str] = None
    ending_date: str
    ending_date_adjusted: bool
    ending_adjustment_reason: Optional[str] = None
    price_field: str
    trading_days: int


class Summary(BaseModel):
    initial_investment: float
    current_holdings_value: float
    total_dividend_income: float
    residual_cash: float
    total_portfolio_value: float
    paper_gain_loss: float
    paper_return_pct: float
    realized_income: float
    realized_sale_proceeds: float
    total_gain_loss: float
    total_return_pct: float
    price_return: float
    income_return: float
    total_return: float
    cost_basis: float
    actual_execution_date: str
    ending_date: str


class HoldingRow(BaseModel):
    ticker: str
    target_weight: float
    normalized_weight: float
    allocated_cash: float
    execution_date: str
    execution_price: float
    shares: float
    cost_basis: float
    ending_price: float
    ending_market_value: float
    price_gain_loss: float
    price_return_pct: float
    total_dividends: float
    dividend_return_pct: float
    total_gain_loss: float
    total_return_pct: float
    current_weight: float
    weight_drift: float
    residual_cash: float


class MonthlyRow(BaseModel):
    month: str
    beginning_value: float
    contributions: float
    dividend_income: float
    realized_sale_proceeds: float
    ending_value: float
    paper_gain_loss: float
    cumulative_dividend_income: float
    total_portfolio_value: float
    monthly_gain_loss: float
    cumulative_gain_loss: float
    monthly_return_pct: float
    cumulative_return_pct: float


class DividendEventRow(BaseModel):
    ticker: str
    ex_date: str
    record_date: Optional[str] = None
    pay_date: Optional[str] = None
    date_type: str
    dividend_per_share: float
    shares_held: float
    dividend_cash: float
    month: str
    cumulative_dividend_cash: float


class DividendByMonth(BaseModel):
    months: list[str]
    tickers: list[str]
    series: dict[str, list[float]]          # ticker -> per-month cash
    totals: list[float]                      # portfolio total per month
    cumulative_total: list[float]


class TimeSeriesPoint(BaseModel):
    date: str
    holdings_value: float
    dividend_cash_period: float
    cumulative_dividends: float
    residual_cash: float
    total_portfolio_value: float
    initial_cash: float
    gain_loss: float
    return_pct: float


class Metadata(BaseModel):
    frequency: str
    time_series_frequency: str
    max_client_frequency: str
    dividend_treatment: str
    allow_fractional_shares: bool
    price_field: str
    timezone: str
    tickers: list[str]
    generated_at: str
    normalization_applied: bool
    weight_sum_before_normalization: float


class CashAnalysisResponse(BaseModel):
    summary: Summary
    execution: ExecutionInfo
    holdings: list[HoldingRow]
    monthly_cash_flows: list[MonthlyRow]
    dividend_events: list[DividendEventRow]
    dividend_by_month: DividendByMonth
    portfolio_time_series: list[TimeSeriesPoint]
    warnings: list[Warning]
    metadata: Metadata
