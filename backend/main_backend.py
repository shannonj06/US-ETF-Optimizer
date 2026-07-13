from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import core
from fastapi import HTTPException
from fastapi.responses import Response

app = FastAPI()

# let the React dev server (localhost:5173 / 3000) call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=core.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def root():
    return {"message": "US ETF Optimizer API is running"}

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

#post request because sending over the data
@app.post("/optimize")
def optimize(request: OptimizeRequest):
    if request.profile not in core.PORTFOLIO_PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    result = core.build_portfolios(request.profile, request.screening, request.score_weights, request.optimizer_weights)
    return core.serialize_optimize(
        result,
        include_charts=request.include_charts,
    )

class EvaluateRequest(BaseModel):
    weights: dict[str, float]
    period: str = "5y"
    rf: float = 0.04

@app.post("/evaluate")
def evaluate(request: EvaluateRequest):
    result = core.evaluate_custom_weights(request.weights, request.period, request.rf)
    return core.serialize_evaluate(result)

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