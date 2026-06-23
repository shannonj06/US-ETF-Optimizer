import sys
from pathlib import Path

# Pages can be loaded directly (deep link / refresh), so ensure the project root
# is importable here too — not just when reached via home.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from build_portfolios import build_portfolios
from config.profiles import PORTFOLIO_PROFILES
from Optimizer_Class.optimizer_weights import OPTIMIZER_CONFIG
from theme import apply_theme, section

apply_theme("Develop a Portfolio",
            "Screen, score, and optimize a US ETF portfolio.")

st.page_link("home.py", label="← Home")

section(1, "Select Portfolio Style")
st.caption("Sets the overall risk/return posture. The screening, scoring, and optimizer values below all default from the style you pick here.")
optimization_type = st.selectbox(
    "Portfolio Style",
    list(PORTFOLIO_PROFILES.keys()),   # real keys: conservative / enhanced / strategic
    format_func=str.title,             # shown as Conservative / Enhanced / Strategic
)
section(2, "Select Screening Values", optional=True)
st.caption("Hard filters applied before scoring: minimum fund size (AUM), max expense ratio, and max duration. ETFs failing any of these are dropped from the universe.")
with st.expander("Screening Values"):
    aum_min = st.number_input("Aum Min", value=PORTFOLIO_PROFILES[optimization_type]["aum_min"])
    max_expense = st.number_input("Max Expense", value=PORTFOLIO_PROFILES[optimization_type]["max_expense"])
    max_duration = st.number_input("Max Duration", value=PORTFOLIO_PROFILES[optimization_type]["max_duration"])

section(3, "Select Scoring Weights", optional=True)
st.caption("How much each metric counts when ranking the screened ETFs to pick the top names. Higher weight = that factor matters more in selection.")
with st.expander("Scoring Weights"):
    s_beta = st.number_input("Beta", value=PORTFOLIO_PROFILES[optimization_type]["score_weights"]['beta'])
    s_yield = st.number_input("Yield", value=PORTFOLIO_PROFILES[optimization_type]["score_weights"]["yield"])
    s_sharpe = st.number_input("Sharpe Ratio", value=PORTFOLIO_PROFILES[optimization_type]["score_weights"]["sharpe"])
    s_aum = st.number_input("AUM", value=PORTFOLIO_PROFILES[optimization_type]["score_weights"]['aum'])
    s_liq = st.number_input("Liquidity", value=PORTFOLIO_PROFILES[optimization_type]["score_weights"]['liq'])
    s_ann_vol = st.number_input("Annual Volatility", value=PORTFOLIO_PROFILES[optimization_type]["score_weights"]['ann_vol'])
    s_expense = st.number_input("Expense Ratio", value=PORTFOLIO_PROFILES[optimization_type]["score_weights"]['expense'])
    s_style = st.number_input("ETF Style", value=PORTFOLIO_PROFILES[optimization_type]["score_weights"]['style'])

section(4, "Select Optimizer Weights", optional=True)
st.caption("How the SLSQP optimizer trades off objectives when setting the final portfolio weights across the selected ETFs.")
with st.expander("Optimizer Weights"):
    o_sharpe = st.number_input("Sharpe Ratio", value=OPTIMIZER_CONFIG[optimization_type]["slsqp_weights"]['sharpe'])
    o_yield = st.number_input("Yield", value=OPTIMIZER_CONFIG[optimization_type]["slsqp_weights"]["yield"])
    o_drawdown = st.number_input("Max Drawdown", value=OPTIMIZER_CONFIG[optimization_type]["slsqp_weights"]["drawdown"])
    o_expense = st.number_input("Expense Ratio", value=OPTIMIZER_CONFIG[optimization_type]["slsqp_weights"]['expense'])
    o_diversification = st.number_input("Diversification", value=OPTIMIZER_CONFIG[optimization_type]["slsqp_weights"]['diversification'])


if st.button("Run Optimization"):
    screening = {"aum_min": aum_min,
                 'max_expense': max_expense,
                 "max_duration": max_duration}
    score_weights = {"beta": s_beta,
                     "yield": s_yield,
                     "sharpe": s_sharpe,
                     "aum": s_aum,
                     "liq": s_liq,
                     "ann_vol": s_ann_vol,
                     "expense": s_expense,
                     "style": s_style}
    optimizer_weights = {"sharpe": o_sharpe,
                         "yield": o_yield,
                         "drawdown": o_drawdown,
                         "expense": o_expense,
                         "diversification": o_diversification}
    with st.spinner("Running optimization… the core-4 brute force can take a few minutes.",
                    show_time=True):
        results_dct = build_portfolios(optimization_type, screening,
                                       score_weights=score_weights, optimizer_weights=optimizer_weights)
    st.session_state.optimizer_results = results_dct
    # remember the inputs so the results page can save a reproducible portfolio
    st.session_state.optimizer_inputs = {
        "profile": optimization_type,
        "screening": screening,
        "score_weights": score_weights,
        "optimizer_weights": optimizer_weights,
    }
    st.switch_page("pages/results.py")
