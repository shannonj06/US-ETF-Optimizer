"""FastAPI application for the ETF optimizer.

Endpoints
---------
GET  /                        liveness ping
GET  /health                  readiness probe (reports data-source reachability)
GET  /markets                 selectable ETF universes
GET  /profiles                selectable portfolio styles
GET  /profiles/{p}/defaults   the numbers that prefill the form
GET  /guest/status            what allowance the calling guest has left
POST /optimize                run the full optimization pipeline
POST /evaluate                score a user-supplied set of weights
POST /api/cash-analysis       historical what-if (see api/routes/cash_analysis.py)

Saved portfolios are **not** served here: the client persists them in Supabase,
where row-level security scopes them to their owner. The old file-backed
/portfolios routes were removed - they shared one JSON file between every
caller with no authentication.

Every expensive endpoint goes through ``access.enforce`` first, which applies
the rate limit and (for signed-out callers) the guest allowance.
"""

import gc
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import access
import core
import guest_policy
import settings
from api.routes.cash_analysis import router as cash_analysis_router
from auth import Identity, resolve_identity
from schemas.optimize import EvaluateRequest, OptimizeRequest
from utils.logger import logger


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _warn_on_insecure_config()
    yield


app = FastAPI(
    title="US ETF Optimizer API",
    description="Screens, optimizes and evaluates ETF portfolios.",
    version="1.0.0",
    lifespan=lifespan,
)

# Browsers may only call this API from these origins. Configured per deployment
# (ALLOWED_ORIGINS) so production isn't stuck with the localhost defaults.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Cash Analysis: POST /api/cash-analysis (service + schemas live under backend/).
app.include_router(cash_analysis_router)


def _warn_on_insecure_config() -> None:
    """Surface deployment mistakes at boot instead of at the first request."""
    if not settings.SUPABASE_CONFIGURED:
        logger.warning(
            "SUPABASE_URL / SUPABASE_ANON_KEY are not set - access tokens cannot "
            "be verified, so every caller is metered as a guest."
        )
    if settings.IS_PRODUCTION:
        if any(origin == "*" for origin in settings.ALLOWED_ORIGINS):
            logger.warning("ALLOWED_ORIGINS contains a wildcard in production.")
        localhost = [o for o in settings.ALLOWED_ORIGINS if "localhost" in o]
        if localhost:
            logger.warning(
                "ALLOWED_ORIGINS still contains localhost entries in production: %s",
                ", ".join(localhost),
            )


def _server_error(action: str, exc: Exception) -> HTTPException:
    """Log the real failure; return a message that leaks nothing.

    Exception text can carry connection strings, file paths and row data. In
    development the detail is passed through, because that is where it's useful.
    """
    logger.exception("%s failed: %s", action, exc)
    detail = (
        f"{action} failed. Please try again; if it keeps happening the market "
        "data provider may be unavailable."
    )
    if not settings.IS_PRODUCTION:
        detail = f"{detail} [dev detail: {type(exc).__name__}: {exc}]"
    return HTTPException(status_code=500, detail=detail)


# -- Liveness / readiness ----------------------------------------------------
@app.get("/")
def root():
    return {"message": "US ETF Optimizer API is running"}


@app.get("/health")
def health():
    """Readiness probe for the platform's health check.

    Only checks that would make the service serve *wrong* results fail the
    probe. Losing MongoDB means no ETF universe, so no endpoint can work -
    that is a 503, and the platform should stop routing here.

    A missing auth configuration is reported but does NOT fail the probe: the
    API still serves every request, metered as a guest. Failing readiness for
    it would put a deployment into a restart loop over a degraded but working
    service.
    """
    checks = {}
    try:
        universe = core.load_etf_data("US")
        checks["etf_universe"] = {
            "ok": True, "rows": int(len(universe)), "critical": True,
        }
    except Exception as exc:
        logger.warning("Health check: ETF universe unavailable: %s", exc)
        checks["etf_universe"] = {
            "ok": False, "error": type(exc).__name__, "critical": True,
        }

    checks["auth"] = {"ok": settings.SUPABASE_CONFIGURED, "critical": False}

    ready = all(c["ok"] for c in checks.values() if c["critical"])
    degraded = any(not c["ok"] for c in checks.values())
    body = {
        "status": "ok" if not degraded else ("degraded" if ready else "unavailable"),
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }
    if not ready:
        raise HTTPException(status_code=503, detail=body)
    return body


# -- Catalogue ---------------------------------------------------------------
@app.get("/markets")
def get_markets():
    """Selectable ETF universes for the frontend's US/Canada switch."""
    return {"markets": core.market_options()}


@app.get("/profiles")
def get_profiles():
    return {"profiles": core.profile_names()}


@app.get("/profiles/{profile_type}/defaults")
def get_default(profile_type: str):
    if profile_type not in core.PORTFOLIO_PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    return core.profile_defaults(profile_type)


@app.get("/guest/status")
def guest_status(identity: Identity = Depends(resolve_identity)):
    """What the caller has left of the guest allowance.

    The client uses this to disable controls and show an accurate banner before
    the user spends a run finding out. It is advisory only - the same limits are
    enforced on every call.
    """
    return access.remaining(identity)


# -- Optimization ------------------------------------------------------------
def _resolve_optimize_inputs(request: OptimizeRequest, identity: Identity) -> dict:
    """Final screening / scoring / optimizer inputs for this run.

    Signed-in callers get their overrides merged over the profile defaults, so a
    partial payload is valid. Guests get the defaults verbatim: the preview shows
    what the profile does, not a hand-tuned configuration.
    """
    defaults = core.profile_defaults(request.profile)
    if identity.is_guest and guest_policy.GUEST_LOCKS_ADVANCED_INPUTS:
        return {
            "screening": dict(defaults["screening"]),
            "score_weights": dict(defaults["score_weights"]),
            "optimizer_weights": dict(defaults["optimizer_weights"]),
            "locked": True,
        }
    return {
        "screening": {**defaults["screening"], **request.screening},
        "score_weights": {**defaults["score_weights"], **request.score_weights},
        "optimizer_weights": {
            **defaults["optimizer_weights"],
            **request.optimizer_weights,
        },
        "locked": False,
    }


@app.post("/optimize")
def optimize(request: OptimizeRequest, identity: Identity = Depends(resolve_identity)):
    if request.profile not in core.PORTFOLIO_PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    market = request.market.upper()
    if market not in core.MARKETS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown market {request.market!r}. "
                f"Expected one of {sorted(core.MARKETS)}."
            ),
        )

    if identity.is_guest:
        try:
            guest_policy.check_optimize(request.profile, market)
        except guest_policy.GuestInputNotAllowed as exc:
            raise access.guest_input_error(exc)

    access.enforce(identity, "optimize")
    inputs = _resolve_optimize_inputs(request, identity)
    logger.info(
        "optimize: %s profile=%s market=%s locked=%s",
        identity.label, request.profile, market, inputs["locked"],
    )

    try:
        result = core.build_portfolios(
            request.profile,
            inputs["screening"],
            inputs["score_weights"],
            inputs["optimizer_weights"],
            market=market,
        )
        payload = core.serialize_optimize(
            result, include_charts=request.include_charts
        )
        payload["inputs_locked"] = inputs["locked"]
        payload["access"] = access.remaining(identity)
        return payload
    except HTTPException:
        raise
    except ValueError as exc:
        # The pipeline raises ValueError for user-fixable problems (nothing
        # survived screening, infeasible constraints).
        access.refund(identity, "optimize")
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        # The run never produced a portfolio, so it shouldn't cost a guest their
        # single preview.
        access.refund(identity, "optimize")
        raise _server_error("Optimization", exc)
    finally:
        # The optimizer builds dozens of matplotlib figures per run. They are
        # closed after encoding, but the Figure/Axes reference cycles are only
        # reclaimed by a full collection - without this the worker grows
        # unbounded across runs and eventually gets OOM-killed.
        gc.collect()


@app.post("/evaluate")
def evaluate(request: EvaluateRequest, identity: Identity = Depends(resolve_identity)):
    if identity.is_guest:
        try:
            guest_policy.check_evaluate(request.weights, request.period, request.rf)
        except guest_policy.GuestInputNotAllowed as exc:
            raise access.guest_input_error(exc)

    access.enforce(identity, "evaluate")
    logger.info(
        "evaluate: %s holdings=%d period=%s",
        identity.label, len(request.weights), request.period,
    )

    try:
        result = core.evaluate_custom_weights(
            request.weights, request.period, request.rf
        )
        payload = core.serialize_evaluate(result)
        payload["access"] = access.remaining(identity)
        return payload
    except HTTPException:
        raise
    except ValueError as exc:
        # User-fixable: every ticker dropped, no overlapping history.
        access.refund(identity, "evaluate")
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        access.refund(identity, "evaluate")
        raise _server_error("Evaluation", exc)
    finally:
        gc.collect()   # same figure reference-cycle cleanup as /optimize
