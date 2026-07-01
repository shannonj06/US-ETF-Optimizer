#here i wanna have a tab for the graphs, run the joint otpimization, a tab for the metrics
import pandas as pd
import streamlit as st
from functions import apply_theme, save_portfolio

apply_theme("Optimization Results", "Weights and metrics for each optimizer.")

results = st.session_state.optimizer_results

st.page_link("home.py", label="← Back Home")

tab1, tab2, tab3 = st.tabs(["CVXPY", "SLSQP", "HRP"])
with tab1:
    st.dataframe(results["cvxpy4"])
    st.subheader("Total Weights")
    st.dataframe(results["cvxpy"])
    st.subheader("Top 4 Metrics")
    st.dataframe(results["cvxpy4_metrics"])
    st.subheader("Total Portfolio Metrics")
    st.dataframe(results["cvxpy_metrics"])

with tab2:
    st.dataframe(results["slsqp4"])
    st.subheader("Total Weights")
    st.dataframe(results["slsqp"])
    st.subheader("Top 4 Metrics")
    st.dataframe(results["slsqp4_metrics"])
    st.subheader("Total Portfolio Metrics")
    st.dataframe(results["slsqp_metrics"])

with tab3:
    st.dataframe(results["hrp4"])
    st.subheader("Total Weights")
    st.dataframe(results["hrp"])
    st.subheader("Top 4 Metrics")
    st.dataframe(results["hrp4_metrics"])
    st.subheader("Total Portfolio Metrics")
    st.dataframe(results["hrp_metrics"])

if st.button("See Portfolio Graphs"):
    st.switch_page("pages/graphs.py")

# ── Save this run ────────────────────────────────────────────────────────────
st.divider()
st.subheader("Save This Portfolio")
inputs = st.session_state.get("optimizer_inputs", {"profile": results.get("profile")})
st.caption(f"Saves the {str(inputs.get('profile', '')).title()} run's weights, "
           "metrics, and settings so you can revisit it from the Home page.")
save_name = st.text_input("Portfolio name",
                          placeholder=f"e.g. {str(inputs.get('profile', 'My')).title()} optimization",
                          key="opt_save_name")
if st.button("💾 Save Portfolio"):
    table_keys = ["slsqp", "slsqp_metrics", "slsqp4", "slsqp4_metrics",
                  "cvxpy", "cvxpy_metrics", "cvxpy4", "cvxpy4_metrics",
                  "hrp", "hrp_metrics", "hrp4", "hrp4_metrics"]
    tables = {k: results[k] for k in table_keys
              if isinstance(results.get(k), pd.DataFrame)}
    # capture the SLSQP full-portfolio charts (the custom-objective optimizer) for the PDF
    slsqp_figs = results.get("slsqp_figs", {})
    chart_labels = {"monte_carlo": "SLSQP — Monte Carlo",
                    "backtest": "SLSQP — Backtest",
                    "walk_forward": "SLSQP — Walk Forward",
                    "rate_hike": "SLSQP — Rate Hike Stress"}
    charts = {lbl: slsqp_figs.get(k) for k, lbl in chart_labels.items()}
    save_portfolio(save_name, "optimization", inputs, tables,
                   meta={"summary": f"{str(inputs.get('profile', '')).title()} profile"},
                   charts=charts)
    st.success("Saved! Find it on the Home page under **Saved Portfolios**.")

