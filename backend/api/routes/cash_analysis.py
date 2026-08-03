"""``POST /cash-analysis`` — run a historical what-if on a portfolio.

Thin route: validation lives in the Pydantic schema, all calculation lives in
``CashAnalysisService``. User-fixable problems (bad tickers, no overlapping data,
collapsed window) come back as ``CashAnalysisError`` and map to HTTP 422 with a
clear message; anything else is an unexpected 500.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas.cash_analysis import CashAnalysisRequest, CashAnalysisResponse
from services import CashAnalysisService, CashAnalysisError

router = APIRouter(prefix="/api", tags=["cash-analysis"])

_service = CashAnalysisService()


@router.post("/cash-analysis", response_model=CashAnalysisResponse)
def run_cash_analysis(request: CashAnalysisRequest):
    try:
        return _service.run(request)
    except CashAnalysisError as exc:
        # Expected, user-fixable input problem.
        raise HTTPException(status_code=422, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - unexpected failure
        raise HTTPException(
            status_code=500,
            detail=f"Cash analysis failed unexpectedly: {exc}",
        )
