"""Single import surface for the Streamlit frontend.

Every backend / helper the pages use is imported and re-exported here, so a page
can just `from functions import build_portfolios, apply_theme, ...` instead of
reaching into build_portfolios / config / Optimizer_Class / theme / storage /
pdf_export individually.

Importing this module also puts the project root on sys.path, so it resolves
whether a page is reached via navigation or loaded directly (deep link / refresh).
"""
import sys
from pathlib import Path

# This file lives in US Optimization/frontend/. The analytics packages
# (build_portfolios, config, Optimizer_Class, …) live one level up at the project
# root; the UI helpers (theme, storage, pdf_export) live alongside this file.
_FRONTEND = Path(__file__).resolve().parent
_ROOT = _FRONTEND.parent
for _p in (_ROOT, _FRONTEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── Analytics / pipeline (project root) ──────────────────────────────────────
from build_portfolios import build_portfolios, evaluate_custom_weights, load_etf_data
from config.profiles import PORTFOLIO_PROFILES
from Optimizer_Class.optimizer_weights import OPTIMIZER_CONFIG

# ── UI helpers (frontend/) ───────────────────────────────────────────────────
from theme import apply_theme, section, show_fig
from storage import load_portfolios, save_portfolio, delete_portfolio, obj_to_df
from pdf_export import build_pdf

__all__ = [
    # pipeline
    "build_portfolios", "evaluate_custom_weights", "load_etf_data",
    # config
    "PORTFOLIO_PROFILES", "OPTIMIZER_CONFIG",
    # theme
    "apply_theme", "section", "show_fig",
    # saved-portfolio storage
    "load_portfolios", "save_portfolio", "delete_portfolio", "obj_to_df",
    # pdf export
    "build_pdf",
]
