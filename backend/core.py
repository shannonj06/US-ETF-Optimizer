
import base64
import io
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")            # headless: a server has no display
import matplotlib.pyplot as plt

# This file lives in US Optimization/backend/. The pipeline + config packages live
# at the project root one level up; storage.py and pdf_export.py live in frontend/.
_BACKEND = Path(__file__).resolve().parent
_ROOT = _BACKEND.parent
_FRONTEND = _ROOT / "frontend"
for _p in (_ROOT, _FRONTEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── Pipeline + config (project root) ─────────────────────────────────────────
from build_portfolios import build_portfolios, evaluate_custom_weights, load_etf_data
from config.profiles import PORTFOLIO_PROFILES
from Optimizer_Class.optimizer_weights import OPTIMIZER_CONFIG

# ── Saved-portfolio storage + PDF (reused from frontend/, both streamlit-free) ─
from storage import load_portfolios, save_portfolio, delete_portfolio, obj_to_df
from pdf_export import build_pdf

__all__ = [
    "build_portfolios", "evaluate_custom_weights", "load_etf_data",
    "PORTFOLIO_PROFILES", "OPTIMIZER_CONFIG",
    "load_portfolios", "save_portfolio", "delete_portfolio", "obj_to_df", "build_pdf",
    "df_records", "fig_to_b64", "figs_to_b64",
    "profile_names", "profile_defaults",
    "serialize_optimize", "serialize_evaluate",
    "ALLOWED_ORIGINS",
]

# ── API settings ─────────────────────────────────────────────────────────────
# Origins allowed to call the API (your React dev servers). Tighten for prod.
ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite
    "http://localhost:3000", 
    "https://us-etf-optimizer.vercel.app",
        # Create React App / Next
]

# Which charts to ship per portfolio, and their display labels.
CHART_LABELS = {
    "monte_carlo":      "Monte Carlo",
    "monte_carlo_dist": "Monte Carlo Distribution",
    "backtest":         "Backtest",
    "walk_forward":     "Walk Forward",
    "rate_hike":        "Rate Hike Stress",
}


# ── Serializers ──────────────────────────────────────────────────────────────
def df_records(df, keep_index=False):
    """DataFrame -> list of row dicts, JSON-safe.

    Routes through pandas' to_json so NaN -> null and numpy scalars -> native.
    Set keep_index=True for the metrics frame (metric names live in the index).
    """
    if keep_index:
        df = df.reset_index()
    return json.loads(df.to_json(orient="records"))


def fig_to_b64(fig):
    """matplotlib Figure -> base64 PNG string (or None). Closes the figure so the
    server doesn't leak memory under load."""
    if fig is None:
        return None
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def figs_to_b64(figs):
    """{chart_key: Figure} -> {chart_key: base64 PNG}, skipping missing charts."""
    return {k: fig_to_b64(figs.get(k)) for k in CHART_LABELS if figs.get(k) is not None}


# ── Profile defaults (for prefilling the React form) ─────────────────────────
def profile_names():
    """The selectable styles: conservative / enhanced / strategic."""
    return list(PORTFOLIO_PROFILES.keys())


def profile_defaults(profile):
    """Default screening / scoring / optimizer values for a profile — the numbers
    Streamlit auto-filled the inputs with."""
    p = PORTFOLIO_PROFILES[profile]
    return {
        "screening": {
            "aum_min":      p["aum_min"],
            "max_expense":  p["max_expense"],
            "max_duration": p["max_duration"],
        },
        "score_weights":     dict(p["score_weights"]),
        "optimizer_weights": dict(OPTIMIZER_CONFIG[profile]["slsqp_weights"]),
    }


# ── Result packagers (shape the /optimize and /evaluate responses) ───────────
def serialize_optimize(result, include_charts=True):
    """build_portfolios() result -> JSON-ready dict (weights + metrics + charts
    for each method, full and core-4)."""
    out = {"profile": result.get("profile"), "methods": {}}
    for method in ("slsqp", "cvxpy", "hrp"):
        block = {
            "weights": df_records(result[method]),
            "metrics": df_records(result[f"{method}_metrics"], keep_index=True),
            "core4": {
                "weights": df_records(result[f"{method}4"]),
                "metrics": df_records(result[f"{method}4_metrics"], keep_index=True),
            },
        }
        if include_charts:
            block["charts"] = figs_to_b64(result[f"{method}_figs"])
            block["core4"]["charts"] = figs_to_b64(result[f"{method}4_figs"])
        out["methods"][method] = block
    return out


def serialize_evaluate(res):
    """evaluate_custom_weights() result -> JSON-ready dict."""
    start, end = res["window"]
    return {
        "weights": df_records(res["weights"]),
        "metrics": df_records(res["metrics"], keep_index=True),
        "dropped": res["dropped"],
        "window":  [str(start), str(end)],
        "charts":  figs_to_b64(res["figs"]),
    }
