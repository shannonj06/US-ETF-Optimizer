"""``POST /api/cash-analysis`` - run a historical what-if on a portfolio.

Thin route: validation lives in the Pydantic schema, all calculation lives in
``CashAnalysisService``. User-fixable problems (bad tickers, no overlapping data,
collapsed window) come back as ``CashAnalysisError`` and map to HTTP 422 with a
clear message; anything else is logged in full and returned as a generic 500.

Access is metered the same way as /optimize and /evaluate: a rate limit for
everyone, plus the single-analysis guest allowance from ``guest_policy``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

import access
import guest_policy
import settings
from auth import Identity, resolve_identity
from schemas.cash_analysis import CashAnalysisRequest, CashAnalysisResponse
from services import CashAnalysisService, CashAnalysisError
from utils.logger import logger

router = APIRouter(prefix="/api", tags=["cash-analysis"])

_service = CashAnalysisService()


@router.post("/cash-analysis", response_model=CashAnalysisResponse)
def run_cash_analysis(
    request: CashAnalysisRequest,
    identity: Identity = Depends(resolve_identity),
):
    if identity.is_guest:
        try:
            guest_policy.check_cash_analysis(
                holdings_count=len(request.portfolio),
                initial_cash=request.initial_cash,
                start=request.requested_start_date,
            )
        except guest_policy.GuestInputNotAllowed as exc:
            raise access.guest_input_error(exc)

    access.enforce(identity, "cash_analysis")
    logger.info(
        "cash-analysis: %s holdings=%d from=%s",
        identity.label, len(request.portfolio), request.requested_start_date,
    )

    try:
        return _service.run(request)
    except CashAnalysisError as exc:
        # Expected, user-fixable input problem - the caller keeps their quota.
        access.refund(identity, "cash_analysis")
        raise HTTPException(status_code=422, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - unexpected failure
        access.refund(identity, "cash_analysis")
        # Never echo the raw exception in production: it can carry connection
        # strings, file paths and row data.
        logger.exception("Cash analysis failed unexpectedly: %s", exc)
        detail = (
            "Cash analysis failed. Please try again; if it keeps happening the "
            "market data provider may be unavailable."
        )
        if not settings.IS_PRODUCTION:
            detail = f"{detail} [dev detail: {type(exc).__name__}: {exc}]"
        raise HTTPException(status_code=500, detail=detail)
