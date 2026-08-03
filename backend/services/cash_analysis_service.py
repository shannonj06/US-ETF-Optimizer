"""Cash Analysis engine.

Given a portfolio (ticker + weight), an initial cash amount and a start date,
simulates buying the portfolio on the first common trading day and holding it
without rebalancing, then reports holdings value, dividends, gains/losses and
total value over time.

Design notes
------------
* **Money math uses ``Decimal``.** All per-holding cash figures (allocation, cost
  basis, dividends, ending value, totals) are computed in ``Decimal`` and only
  rounded to presentation precision at the API boundary. The daily time series is
  computed in float for speed (it drives charts, not accounting) but is derived
  from the same prices, so it agrees with the Decimal summary to the cent.
* **No double-counting of dividends.** Price appreciation uses the unadjusted
  "Close"; income uses the separate actual per-share dividend events. See
  ``repositories/_yf.py``.
* **No look-ahead.** The portfolio is initialized on the first common trading day
  on/after the requested start using that day's price. A dividend is credited
  only if its ex-date is strictly AFTER the execution date (you must own the
  shares before the ex-date to be entitled), and on/before the ending date.
* **No rebalancing / no sales** in this version, so realized capital gains are
  always zero and share counts stay constant (dividends are cash by default).
  The structure leaves room for reinvestment and sales later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, getcontext, localcontext

import pandas as pd

from repositories import MarketDataRepository, DividendRepository
from repositories._yf import MARKET_TIMEZONE
from schemas.cash_analysis import CashAnalysisRequest

getcontext().prec = 28

# Weight-normalization thresholds (relative to the inferred 1.0 / 100% basis).
_NEGLIGIBLE_DIFF = Decimal("0.0005")   # below this: normalize silently
_MATERIAL_DIFF = Decimal("0.02")       # above this: warn before normalizing

# Above this many trading days we stop emitting a daily series and emit monthly
# instead, so a multi-year window doesn't ship tens of thousands of points.
_MAX_DAILY_POINTS = 1500

_ZERO = Decimal("0")
_CENT = Decimal("0.01")


class CashAnalysisError(ValueError):
    """Raised for user-fixable problems (bad tickers, no data, empty window)."""


@dataclass
class _Holding:
    ticker: str
    target_weight: Decimal
    normalized_weight: Decimal
    allocated_cash: Decimal
    execution_price: Decimal
    shares: Decimal
    cost_basis: Decimal
    residual_cash: Decimal
    ending_price: Decimal
    ending_market_value: Decimal
    total_dividends: Decimal


# ── small numeric helpers ────────────────────────────────────────────────────
def _dec(x) -> Decimal:
    return Decimal(str(x))


def _money(x: Decimal) -> float:
    return float(x.quantize(_CENT, rounding=ROUND_HALF_UP))


def _round(x: Decimal | float, places: int) -> float:
    q = Decimal(10) ** -places
    return float(_dec(x).quantize(q, rounding=ROUND_HALF_UP))


def _safe_div(num: Decimal, den: Decimal) -> Decimal:
    return num / den if den != 0 else _ZERO


class CashAnalysisService:
    def __init__(self, market_repo=None, dividend_repo=None):
        self.market_repo = market_repo or MarketDataRepository()
        self.dividend_repo = dividend_repo or DividendRepository()

    # ── public entry point ───────────────────────────────────────────────────
    def run(self, request: CashAnalysisRequest) -> dict:
        warnings: list[dict] = []
        tickers = [h.ticker for h in request.portfolio]

        # 1. Normalize weights (+ material-difference warning).
        norm_weights, weight_meta = self._normalize_weights(request.portfolio, warnings)

        # 2. Fetch the shared price panel across the full requested window.
        end_for_fetch = request.end_date or date.today()
        panel = self.market_repo.get_price_panel(
            tickers, request.requested_start_date, end_for_fetch
        )
        if panel.missing:
            raise CashAnalysisError(
                "No historical price data found for: "
                + ", ".join(sorted(panel.missing))
                + ". Check the ticker symbols."
            )
        if panel.prices.empty:
            raise CashAnalysisError(
                "The selected ETFs have no overlapping trading history in this window."
            )

        # 3. Resolve execution + ending dates on the common trading calendar.
        exec_date = self.market_repo.common_execution_date(panel, request.requested_start_date)
        if exec_date is None:
            raise CashAnalysisError(
                "No common trading day exists on or after the requested start date "
                "for all selected ETFs."
            )
        exec_info = self._resolve_execution(request, panel, exec_date, warnings)

        ending_date = pd.Timestamp(exec_info["ending_date"])
        window = panel.prices.loc[exec_date:ending_date]
        if len(window) < 1:
            raise CashAnalysisError("The analysis window contains no trading days.")

        # 4. Dividend events (actual per-share), across the whole window.
        div_data = self.dividend_repo.get_dividends(tickers, exec_date, ending_date)
        if len(div_data.no_dividends) == len(tickers):
            warnings.append({
                "code": "no_dividend_data",
                "severity": "info",
                "message": "No dividend distributions were found for any holding in "
                           "this period. Income return is $0.",
            })

        # 5. Build per-holding results (Decimal money math).
        holdings, totals = self._build_holdings(
            request, norm_weights, panel, exec_date, ending_date, div_data, warnings
        )

        # 6. Time series (float, daily or monthly depending on length).
        time_series, ts_freq = self._build_time_series(
            request, window, holdings, div_data, exec_date, ending_date, totals, warnings
        )

        # 7. Monthly cash-flow table (always monthly).
        monthly = self._build_monthly(
            window, holdings, div_data, exec_date, ending_date, totals, request
        )

        # 8. Dividend tables (events + by-month matrix).
        div_events, div_by_month = self._build_dividends(
            tickers, holdings, div_data, exec_date, ending_date
        )

        summary = self._build_summary(request, totals, exec_date, ending_date)

        metadata = {
            "frequency": request.frequency,
            "time_series_frequency": ts_freq,
            "max_client_frequency": ts_freq,
            "dividend_treatment": request.dividend_treatment,
            "allow_fractional_shares": request.allow_fractional_shares,
            "price_field": "unadjusted_close",
            "timezone": MARKET_TIMEZONE,
            "tickers": tickers,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "normalization_applied": weight_meta["normalization_applied"],
            "weight_sum_before_normalization": weight_meta["raw_sum"],
        }

        return {
            "summary": summary,
            "execution": exec_info,
            "holdings": [
                self._holding_row(h, totals, str(exec_date.date())) for h in holdings
            ],
            "monthly_cash_flows": monthly,
            "dividend_events": div_events,
            "dividend_by_month": div_by_month,
            "portfolio_time_series": time_series,
            "warnings": warnings,
            "metadata": metadata,
        }

    # ── steps ────────────────────────────────────────────────────────────────
    def _normalize_weights(self, portfolio, warnings) -> tuple[dict[str, Decimal], dict]:
        weights = {h.ticker: _dec(h.weight) for h in portfolio}
        raw_sum = sum(weights.values(), _ZERO)
        if raw_sum <= 0:
            raise CashAnalysisError("Portfolio weights sum to zero.")

        # Infer whether weights were entered as fractions (~1) or percents (~100).
        target = Decimal("1") if abs(raw_sum - 1) <= abs(raw_sum - 100) else Decimal("100")
        rel_diff = abs(raw_sum - target) / target

        normalized = {t: w / raw_sum for t, w in weights.items()}
        normalization_applied = rel_diff > _NEGLIGIBLE_DIFF

        if rel_diff > _MATERIAL_DIFF:
            shown = f"{raw_sum:.4f}" if target == 1 else f"{raw_sum:.2f}%"
            warnings.append({
                "code": "weights_normalized_material",
                "severity": "warning",
                "message": (
                    f"Portfolio weights summed to {shown}, which differs materially "
                    f"from {'100%' if target == 100 else '1.0'}. They were normalized "
                    "to total 100% before running the analysis."
                ),
            })
        elif normalization_applied:
            warnings.append({
                "code": "weights_normalized_minor",
                "severity": "info",
                "message": "Portfolio weights were normalized to total 100% "
                           "(small rounding difference).",
            })

        return normalized, {
            "normalization_applied": normalization_applied,
            "raw_sum": float(raw_sum),
        }

    def _resolve_execution(self, request, panel, exec_date, warnings) -> dict:
        requested = pd.Timestamp(request.requested_start_date).normalize()
        date_adjusted = exec_date != requested
        reason = None

        if date_adjusted:
            late = {t: fd for t, fd in panel.first_dates.items() if fd > requested}
            if late:
                names = ", ".join(sorted(late))
                reason = (
                    f"{names} did not have pricing on the requested start date "
                    f"(inception/first data later than requested). Execution moved to "
                    f"{exec_date.date()}, the first day all holdings had prices."
                )
                warnings.append({
                    "code": "execution_date_inception",
                    "severity": "warning",
                    "message": reason,
                })
            else:
                reason = (
                    f"The requested start date {requested.date()} was not a trading day "
                    f"for all holdings. Execution moved to the next common trading day, "
                    f"{exec_date.date()}."
                )
                warnings.append({
                    "code": "execution_date_adjusted",
                    "severity": "info",
                    "message": reason,
                })

        # Ending date.
        requested_end = request.end_date
        ending = self.market_repo.last_common_valid_date(
            panel, requested_end or self.market_repo.latest_available_date(panel)
        )
        ending_adjusted = False
        ending_reason = None
        if ending is None or ending <= exec_date:
            raise CashAnalysisError(
                "The analysis end date is not after the execution date once adjusted "
                "to valid trading days. Choose a later end date."
            )
        if requested_end is not None:
            req_end_ts = pd.Timestamp(requested_end).normalize()
            if ending < req_end_ts:
                ending_adjusted = True
                ending_reason = (
                    f"No market data was available through {req_end_ts.date()}; the "
                    f"analysis ends on {ending.date()}, the last common trading day "
                    "with valid pricing."
                )
                warnings.append({
                    "code": "ending_date_adjusted",
                    "severity": "info",
                    "message": ending_reason,
                })

        return {
            "requested_start_date": str(request.requested_start_date),
            "actual_execution_date": str(exec_date.date()),
            "date_adjusted": bool(date_adjusted),
            "adjustment_reason": reason,
            "requested_end_date": str(requested_end) if requested_end else None,
            "ending_date": str(ending.date()),
            "ending_date_adjusted": ending_adjusted,
            "ending_adjustment_reason": ending_reason,
            "price_field": "unadjusted_close",
            "trading_days": int(len(panel.prices.loc[exec_date:ending])),
        }

    def _dividends_for_ticker(self, div_data, ticker, exec_date, ending_date):
        """Events entitling the holder: ex-date strictly after execution, on/before end."""
        return [
            e for e in div_data.events
            if e.ticker == ticker and exec_date < e.ex_date <= ending_date
        ]

    def _build_holdings(self, request, norm_weights, panel, exec_date, ending_date,
                        div_data, warnings):
        initial_cash = _dec(request.initial_cash)
        fractional = request.allow_fractional_shares
        holdings: list[_Holding] = []

        with localcontext() as ctx:
            ctx.prec = 28
            for h in request.portfolio:
                t = h.ticker
                nw = norm_weights[t]
                alloc = initial_cash * nw
                exec_price = _dec(panel.prices.at[exec_date, t])
                ending_price = _dec(panel.prices.at[ending_date, t])

                if fractional:
                    shares = alloc / exec_price
                    cost_basis = shares * exec_price
                    residual = alloc - cost_basis
                    if abs(residual) < Decimal("0.005"):
                        residual = _ZERO
                        cost_basis = alloc
                else:
                    whole = (alloc / exec_price).to_integral_value(rounding="ROUND_FLOOR")
                    shares = whole
                    cost_basis = shares * exec_price
                    residual = alloc - cost_basis
                    if shares == 0:
                        warnings.append({
                            "code": "insufficient_cash_for_share",
                            "severity": "warning",
                            "message": (
                                f"{t}: allocated ${_money(alloc)} was not enough to buy a "
                                f"whole share at ${_money(exec_price)} (fractional shares "
                                "disabled). This holding bought 0 shares."
                            ),
                        })

                ending_mv = shares * ending_price

                divs = self._dividends_for_ticker(div_data, t, exec_date, ending_date)
                total_div = sum((shares * _dec(e.dividend_per_share) for e in divs), _ZERO)

                holdings.append(_Holding(
                    ticker=t,
                    target_weight=nw,             # normalized target (sums to 1)
                    normalized_weight=nw,
                    allocated_cash=alloc,
                    execution_price=exec_price,
                    shares=shares,
                    cost_basis=cost_basis,
                    residual_cash=residual,
                    ending_price=ending_price,
                    ending_market_value=ending_mv,
                    total_dividends=total_div,
                ))

        totals = self._portfolio_totals(request, holdings)
        return holdings, totals

    def _portfolio_totals(self, request, holdings) -> dict:
        initial_cash = _dec(request.initial_cash)
        current_holdings = sum((h.ending_market_value for h in holdings), _ZERO)
        cost_basis = sum((h.cost_basis for h in holdings), _ZERO)
        residual = sum((h.residual_cash for h in holdings), _ZERO)
        dividends = sum((h.total_dividends for h in holdings), _ZERO)

        realized_sale_proceeds = _ZERO      # no sales in this version
        total_pv = current_holdings + dividends + residual + realized_sale_proceeds
        paper_gl = current_holdings - cost_basis
        total_gl = total_pv - initial_cash
        price_return = current_holdings - cost_basis
        income_return = dividends

        return {
            "initial_cash": initial_cash,
            "current_holdings": current_holdings,
            "cost_basis": cost_basis,
            "residual": residual,
            "dividends": dividends,
            "realized_sale_proceeds": realized_sale_proceeds,
            "total_pv": total_pv,
            "paper_gl": paper_gl,
            "total_gl": total_gl,
            "price_return": price_return,
            "income_return": income_return,
        }

    def _build_summary(self, request, totals, exec_date, ending_date) -> dict:
        t = totals
        return {
            "initial_investment": _money(t["initial_cash"]),
            "current_holdings_value": _money(t["current_holdings"]),
            "total_dividend_income": _money(t["dividends"]),
            "residual_cash": _money(t["residual"]),
            "total_portfolio_value": _money(t["total_pv"]),
            "paper_gain_loss": _money(t["paper_gl"]),
            "paper_return_pct": _round(_safe_div(t["paper_gl"], t["cost_basis"]) * 100, 4),
            "realized_income": _money(t["income_return"]),
            "realized_sale_proceeds": _money(t["realized_sale_proceeds"]),
            "total_gain_loss": _money(t["total_gl"]),
            "total_return_pct": _round(_safe_div(t["total_gl"], t["initial_cash"]) * 100, 4),
            "price_return": _money(t["price_return"]),
            "income_return": _money(t["income_return"]),
            "total_return": _money(t["price_return"] + t["income_return"]),
            "cost_basis": _money(t["cost_basis"]),
            "actual_execution_date": str(exec_date.date()),
            "ending_date": str(ending_date.date()),
        }

    def _holding_row(self, h: _Holding, totals, execution_date: str) -> dict:
        total_ending = totals["current_holdings"]
        current_weight = _safe_div(h.ending_market_value, total_ending)
        price_gl = h.ending_market_value - h.cost_basis
        total_gl = price_gl + h.total_dividends
        return {
            "ticker": h.ticker,
            "target_weight": _round(h.target_weight * 100, 4),
            "normalized_weight": _round(h.normalized_weight * 100, 4),
            "allocated_cash": _money(h.allocated_cash),
            "execution_date": execution_date,
            "execution_price": _round(h.execution_price, 4),
            "shares": _round(h.shares, 6),
            "cost_basis": _money(h.cost_basis),
            "ending_price": _round(h.ending_price, 4),
            "ending_market_value": _money(h.ending_market_value),
            "price_gain_loss": _money(price_gl),
            "price_return_pct": _round(_safe_div(price_gl, h.cost_basis) * 100, 4),
            "total_dividends": _money(h.total_dividends),
            "dividend_return_pct": _round(_safe_div(h.total_dividends, h.cost_basis) * 100, 4),
            "total_gain_loss": _money(total_gl),
            "total_return_pct": _round(_safe_div(total_gl, h.cost_basis) * 100, 4),
            "current_weight": _round(current_weight * 100, 4),
            "weight_drift": _round((current_weight - h.target_weight) * 100, 4),
            "residual_cash": _money(h.residual_cash),
        }

    # ── time series ──────────────────────────────────────────────────────────
    def _cumulative_dividend_series(self, index, holdings, div_data, exec_date, ending_date):
        """A per-date cumulative dividend-cash Series aligned to ``index``."""
        shares = {h.ticker: h.shares for h in holdings}
        cash_by_date: dict[pd.Timestamp, Decimal] = {}
        for e in div_data.events:
            if exec_date < e.ex_date <= ending_date:
                amt = shares.get(e.ticker, _ZERO) * _dec(e.dividend_per_share)
                cash_by_date[e.ex_date] = cash_by_date.get(e.ex_date, _ZERO) + amt

        if not cash_by_date:
            return pd.Series(0.0, index=index)

        ex_dates = sorted(cash_by_date)
        running = _ZERO
        cum_at: list[tuple[pd.Timestamp, float]] = []
        for d in ex_dates:
            running += cash_by_date[d]
            cum_at.append((d, float(running)))

        # step function: value at date t = cumulative cash for all ex-dates <= t
        cum = pd.Series(0.0, index=index)
        j = 0
        current = 0.0
        for i, t in enumerate(index):
            while j < len(cum_at) and cum_at[j][0] <= t:
                current = cum_at[j][1]
                j += 1
            cum.iloc[i] = current
        return cum

    def _build_time_series(self, request, window, holdings, div_data, exec_date,
                           ending_date, totals, warnings):
        shares = {h.ticker: float(h.shares) for h in holdings}
        residual = float(totals["residual"])
        initial_cash = float(totals["initial_cash"])

        # holdings value per date = sum shares_i * close_i
        cols = [h.ticker for h in holdings]
        holdings_value = window[cols].mul(pd.Series(shares)).sum(axis=1)
        cum_div = self._cumulative_dividend_series(
            window.index, holdings, div_data, exec_date, ending_date
        )

        n = len(window.index)
        if n > _MAX_DAILY_POINTS:
            ts_freq = "monthly"
            # keep the last trading day of each month (plus the very first point)
            month_ends = window.index.to_series().groupby(
                [window.index.year, window.index.month]
            ).max().tolist()
            keep = sorted(set([window.index[0]] + month_ends))
            warnings.append({
                "code": "time_series_downsampled",
                "severity": "info",
                "message": (
                    f"The analysis window spans {n} trading days; the time-series chart "
                    "is aggregated to month-end points to keep it responsive."
                ),
            })
        else:
            ts_freq = "daily"
            keep = list(window.index)

        points = []
        prev_cum = 0.0
        for t in keep:
            hv = float(holdings_value.loc[t])
            cd = float(cum_div.loc[t])
            total_pv = hv + cd + residual
            gl = total_pv - initial_cash
            points.append({
                "date": str(pd.Timestamp(t).date()),
                "holdings_value": _round(hv, 2),
                "dividend_cash_period": _round(cd - prev_cum, 2),
                "cumulative_dividends": _round(cd, 2),
                "residual_cash": _round(residual, 2),
                "total_portfolio_value": _round(total_pv, 2),
                "initial_cash": _round(initial_cash, 2),
                "gain_loss": _round(gl, 2),
                "return_pct": _round((gl / initial_cash * 100) if initial_cash else 0, 4),
            })
            prev_cum = cd
        return points, ts_freq

    # ── monthly table ────────────────────────────────────────────────────────
    def _build_monthly(self, window, holdings, div_data, exec_date, ending_date,
                       totals, request):
        shares = {h.ticker: float(h.shares) for h in holdings}
        cols = [h.ticker for h in holdings]
        holdings_value = window[cols].mul(pd.Series(shares)).sum(axis=1)
        cum_div = self._cumulative_dividend_series(
            window.index, holdings, div_data, exec_date, ending_date
        )

        residual = float(totals["residual"])
        cost_basis = float(totals["cost_basis"])
        initial_cash = float(totals["initial_cash"])

        # month-end trading day per calendar month in the window
        month_end = window.index.to_series().groupby(
            [window.index.year, window.index.month]
        ).max().sort_values().tolist()

        rows = []
        prev_ending_value = cost_basis      # first month's "beginning" = value at execution
        prev_cum_div = 0.0
        prev_total_pv = initial_cash
        for i, t in enumerate(month_end):
            t = pd.Timestamp(t)
            ending_value = float(holdings_value.loc[t])
            cumulative_div = float(cum_div.loc[t])
            total_pv = ending_value + cumulative_div + residual
            contributions = initial_cash if i == 0 else 0.0
            div_income = cumulative_div - prev_cum_div
            paper_gl = ending_value - cost_basis
            monthly_gl = total_pv - prev_total_pv
            cumulative_gl = total_pv - initial_cash
            denom = prev_total_pv if prev_total_pv else initial_cash
            rows.append({
                "month": f"{t.year:04d}-{t.month:02d}",
                "beginning_value": _round(prev_ending_value, 2),
                "contributions": _round(contributions, 2),
                "dividend_income": _round(div_income, 2),
                "realized_sale_proceeds": 0.0,
                "ending_value": _round(ending_value, 2),
                "paper_gain_loss": _round(paper_gl, 2),
                "cumulative_dividend_income": _round(cumulative_div, 2),
                "total_portfolio_value": _round(total_pv, 2),
                "monthly_gain_loss": _round(monthly_gl, 2),
                "cumulative_gain_loss": _round(cumulative_gl, 2),
                "monthly_return_pct": _round((monthly_gl / denom * 100) if denom else 0, 4),
                "cumulative_return_pct": _round(
                    (cumulative_gl / initial_cash * 100) if initial_cash else 0, 4),
            })
            prev_ending_value = ending_value
            prev_cum_div = cumulative_div
            prev_total_pv = total_pv
        return rows

    # ── dividend tables ──────────────────────────────────────────────────────
    def _build_dividends(self, tickers, holdings, div_data, exec_date, ending_date):
        shares = {h.ticker: h.shares for h in holdings}

        entitled = [
            e for e in div_data.events if exec_date < e.ex_date <= ending_date
        ]
        entitled.sort(key=lambda e: (e.ex_date, e.ticker))

        events_rows = []
        running = _ZERO
        for e in entitled:
            sh = shares.get(e.ticker, _ZERO)
            cash = sh * _dec(e.dividend_per_share)
            running += cash
            events_rows.append({
                "ticker": e.ticker,
                "ex_date": str(e.ex_date.date()),
                "record_date": str(e.record_date.date()) if e.record_date else None,
                "pay_date": str(e.pay_date.date()) if e.pay_date else None,
                "date_type": e.date_type,
                "dividend_per_share": _round(e.dividend_per_share, 6),
                "shares_held": _round(sh, 6),
                "dividend_cash": _money(cash),
                "month": f"{e.ex_date.year:04d}-{e.ex_date.month:02d}",
                "cumulative_dividend_cash": _money(running),
            })

        # by-month matrix spanning EVERY month in the window (incl. zero months)
        months = [
            f"{p.year:04d}-{p.month:02d}"
            for p in pd.period_range(exec_date, ending_date, freq="M")
        ]
        month_index = {m: i for i, m in enumerate(months)}
        series = {t: [0.0] * len(months) for t in tickers}
        for row in events_rows:
            idx = month_index.get(row["month"])
            if idx is not None:
                series[row["ticker"]][idx] += row["dividend_cash"]

        totals_by_month = [
            _round(sum(series[t][i] for t in tickers), 2) for i in range(len(months))
        ]
        cumulative = []
        run = 0.0
        for v in totals_by_month:
            run += v
            cumulative.append(_round(run, 2))

        series = {t: [_round(v, 2) for v in vals] for t, vals in series.items()}
        by_month = {
            "months": months,
            "tickers": list(tickers),
            "series": series,
            "totals": totals_by_month,
            "cumulative_total": cumulative,
        }
        return events_rows, by_month
