import streamlit as st
from theme import apply_theme, show_fig

apply_theme("Portfolio Graphs",
            "Compare optimizers across every chart — side by side, one view at a time.")

results = st.session_state.optimizer_results

# Chart types (key in the *_figs dicts -> human label).
CHARTS = [
    ("monte_carlo",      "Monte Carlo"),
    ("monte_carlo_dist", "Monte Carlo Distribution"),
    ("backtest",         "Backtest"),
    ("walk_forward",     "Walk Forward"),
    ("rate_hike",        "Rate Hike Stress"),
]

# Optimizer (label -> key prefix). The "4" variants are the top-4 holdings;
# the plain key is the total portfolio.
OPTIMIZERS = [
    ("CVXPY", "cvxpy"),
    ("SLSQP", "slsqp"),
    ("HRP",   "hrp"),
]

top_link, _ = st.columns([1, 9])
with top_link:
    st.page_link("pages/results.py", label="← Back to Results")

# One toggle controls whether we're looking at the concentrated top-4 sleeve
# or the full portfolio — applied across all charts so comparisons stay honest.
scope = st.radio(
    "Portfolio scope",
    ["Top 4 holdings", "Total portfolio"],
    horizontal=True,
)
suffix = "4_figs" if scope == "Top 4 holdings" else "_figs"

st.caption(
    "Each tab is one chart type. The three columns are the optimizers, so you "
    "can read them across without the page losing its shape."
)

# One tab per chart type. Inside each tab the three optimizers sit in equal
# columns — readable on any screen, and the orientation never breaks because
# we never go wider than three.
tabs = st.tabs([label for _, label in CHARTS])
for tab, (chart_key, chart_label) in zip(tabs, CHARTS):
    with tab:
        st.subheader(chart_label)
        cols = st.columns(3, gap="large")
        for col, (opt_label, opt_key) in zip(cols, OPTIMIZERS):
            with col:
                st.markdown(
                    f"<div class='im-card-title'>{opt_label}</div>",
                    unsafe_allow_html=True,
                )
                fig = results[f"{opt_key}{suffix}"][chart_key]
                show_fig(fig)
