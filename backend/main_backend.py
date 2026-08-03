import gc

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import core
from fastapi import HTTPException
from fastapi.responses import Response

from api.routes.cash_analysis import router as cash_analysis_router

app = FastAPI()

# let the React dev server (localhost:5173 / 3000) call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=core.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Cash Analysis: POST /api/cash-analysis (service + schemas live under backend/).
app.include_router(cash_analysis_router)


@app.get("/")
def root():
    return {"message": "US ETF Optimizer API is running"}

@app.get("/markets")
def get_markets():
    """Selectable ETF universes for the frontend's US/Canada switch."""
    return {"markets": core.market_options()}

@app.get("/profiles")
def get_profiles():
    return {
    "profiles": core.profile_names()
}

@app.get("/profiles/{profile_type}/defaults")
def get_default(profile_type):
    if profile_type not in core.PORTFOLIO_PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    return core.profile_defaults(profile_type)

#this class holds the formatting of the parameters being sent with the request
#create a class for every post request
class OptimizeRequest(BaseModel):
    profile: str
    screening: dict
    score_weights: dict
    optimizer_weights: dict
    include_charts: bool = True
    market: str = "US"          # "US" or "CA" — which ETF universe to optimize

#post request because sending over the data
@app.post("/optimize")
def optimize(request: OptimizeRequest):
    if request.profile not in core.PORTFOLIO_PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    market = request.market.upper()
    if market not in core.MARKETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown market '{request.market}'. Expected one of {sorted(core.MARKETS)}.",
        )
    try:
        result = core.build_portfolios(
            request.profile, request.screening, request.score_weights,
            request.optimizer_weights, market=market,
        )
        return core.serialize_optimize(
            result,
            include_charts=request.include_charts,
        )
    finally:
        # The optimizer builds dozens of matplotlib figures per run. They are
        # closed after encoding, but the Figure/Axes reference cycles are only
        # reclaimed by a full collection — without this the worker grows
        # unbounded across runs and eventually gets OOM-killed.
        gc.collect()

class EvaluateRequest(BaseModel):
    weights: dict[str, float]
    period: str = "5y"
    rf: float = 0.04

@app.post("/evaluate")
def evaluate(request: EvaluateRequest):
    try:
        result = core.evaluate_custom_weights(request.weights, request.period, request.rf)
        return core.serialize_evaluate(result)
    finally:
        gc.collect()   # same figure reference-cycle cleanup as /optimize

@app.get("/portfolios")
def get_portfolios():
    return core.load_portfolios()

class PortfolioRequest(BaseModel):
    name: str
    ptype: str
    inputs: dict
    tables: dict
    meta: dict = None
    charts: dict = None

@app.post("/portfolios")
def add_portfolio(request: PortfolioRequest):
    return core.save_portfolio(request.name, request.ptype, request.inputs, request.tables, request.meta, request.charts)
  
@app.delete("/portfolios/{portfolio_id}")
def delete_portfolio(portfolio_id: str):
    portfolios = core.load_portfolios()
    portfolio = next(
        (p for p in portfolios if p.get("id") == portfolio_id),
        None,
    )
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    core.delete_portfolio(portfolio_id)
    return {
        "ok": True,
        "deleted_id": portfolio_id,
    }

@app.get("/portfolios/{portfolio_id}/pdf")
def get_portfolio_pdf(portfolio_id: str):
    portfolios = core.load_portfolios()
    portfolio = next(
        (p for p in portfolios if p.get("id") == portfolio_id),
        None,
    )
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    pdf_bytes = core.build_pdf(portfolio)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{portfolio["name"]}.pdf"'
        },
    )