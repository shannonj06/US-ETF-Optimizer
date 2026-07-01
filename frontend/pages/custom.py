import sys
from pathlib import Path

# Pages can be loaded directly (deep link / refresh), so ensure the project root
# is importable here too — not just when reached via home.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from functions import evaluate_custom_weights, save_portfolio, apply_theme, section, show_fig

apply_theme("Input Your Portfolio",
            "Enter the ETFs you hold and get the same metrics and stress charts as the optimizer.")

st.page_link("home.py", label="← Home")

# ── Holdings state ───────────────────────────────────────────────────────────
# Each holding keeps a STABLE id so the per-row widget keys (tk_<id>, wt_<id>)
# don't shift when a row is removed — the classic Streamlit dynamic-list trap.
if "holdings" not in st.session_state:
    st.session_state.holdings = [{"id": 0, "ticker": "", "weight": 1.0}]
    st.session_state.next_id = 1
# Pre-seed the settings widgets so we can later overwrite them on reopen without
# tripping Streamlit's "default value + session_state" warning.
st.session_state.setdefault("custom_period", "5y")
st.session_state.setdefault("custom_rf", 0.04)

# Reopening a saved custom portfolio drops its tickers/weights straight into the
# builder (fresh ids so we never collide with stale widget keys).
if st.session_state.get("reopen_custom"):
    inp = st.session_state.pop("reopen_custom")
    holdings = []
    for tk, wt in inp.get("weights", {}).items():
        holdings.append({"id": st.session_state.next_id, "ticker": tk, "weight": float(wt)})
        st.session_state.next_id += 1
    st.session_state.holdings = holdings or [{"id": st.session_state.next_id, "ticker": "", "weight": 1.0}]
    st.session_state["custom_period"] = inp.get("period", "5y")
    st.session_state["custom_rf"] = float(inp.get("rf", 0.04))
    st.session_state.pop("custom_results", None)

# ── Holdings editor ──────────────────────────────────────────────────────────
section(1, "Add Your Holdings")
st.caption("Add a ticker for each ETF you hold. Weights are normalized automatically — one ETF is 100%, two equal weights are 50/50 — and you can re-tilt any weight.")

remove_id = None
for n, h in enumerate(st.session_state.holdings, start=1):
    i = h["id"]
    c_num, c_tk, c_wt, c_rm = st.columns([0.5, 5, 2, 1], vertical_alignment="center")
    with c_num:
        st.markdown(f"<div class='im-rownum'>{n}</div>", unsafe_allow_html=True)
    with c_tk:
        st.text_input("Ticker", value=h.get("ticker", ""), key=f"tk_{i}",
                      placeholder="e.g. SHV", label_visibility="collapsed")
    with c_wt:
        st.number_input("Weight", min_value=0.0, step=0.5,
                        value=float(h.get("weight", 1.0)), key=f"wt_{i}",
                        label_visibility="collapsed")
    with c_rm:
        if st.button("✕", key=f"rm_{i}", help="Remove this ticker",
                     disabled=len(st.session_state.holdings) == 1):
            remove_id = i

if remove_id is not None:
    st.session_state.holdings = [x for x in st.session_state.holdings if x["id"] != remove_id]
    st.session_state.pop(f"tk_{remove_id}", None)
    st.session_state.pop(f"wt_{remove_id}", None)
    st.rerun()

c_add, _ = st.columns([2, 8])
with c_add:
    if st.button("➕ Add Ticker"):
        st.session_state.holdings.append(
            {"id": st.session_state.next_id, "ticker": "", "weight": 1.0})
        st.session_state.next_id += 1
        st.rerun()

# Collect the current rows straight from the widget state and normalize.
agg = {}
for h in st.session_state.holdings:
    i = h["id"]
    tk = str(st.session_state.get(f"tk_{i}", "")).strip().upper()
    wt = float(st.session_state.get(f"wt_{i}", 0) or 0)
    if tk and wt > 0:
        agg[tk] = agg.get(tk, 0.0) + wt

total = sum(agg.values())
if agg:
    preview = pd.DataFrame(
        [{"Ticker": t, "Weight": w, "Normalized %": w / total * 100}
         for t, w in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)]
    )
    st.markdown("**Normalized allocation**")
    st.dataframe(
        preview, hide_index=True, use_container_width=True,
        column_config={
            "Weight": st.column_config.NumberColumn(format="%.2f"),
            "Normalized %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# ── Settings ─────────────────────────────────────────────────────────────────
section(2, "Settings", optional=True)
cset1, cset2 = st.columns(2)
with cset1:
    period = st.selectbox("History window", ["1y", "2y", "3y", "5y", "10y"],
                          key="custom_period")
with cset2:
    rf = st.number_input("Risk-free rate", step=0.01, format="%.3f",
                         key="custom_rf")

if st.button("Evaluate Portfolio", type="primary"):
    if not agg:
        st.error("Add at least one ticker with a positive weight.")
    else:
        with st.spinner("Fetching prices and computing metrics…", show_time=True):
            try:
                res = evaluate_custom_weights(agg, period=period, rf=rf)
            except Exception as e:
                res = None
                st.error(f"Could not evaluate the portfolio: {e}")
        if res is not None:
            st.session_state.custom_results = {
                "res": res,
                "inputs": {"weights": agg, "period": period, "rf": rf},
            }

# ── Results (persisted so the Save button's rerun doesn't wipe them) ─────────
cr = st.session_state.get("custom_results")
if cr:
    res, inputs = cr["res"], cr["inputs"]
    if res["dropped"]:
        st.warning(f"No usable price history — dropped: {', '.join(res['dropped'])}")
    start, end = res["window"]
    st.caption(f"Window: {start} → {end}  ·  rf = {inputs['rf']:.2%}")

    cwa, cwb = st.columns(2)
    with cwa:
        st.subheader("Normalized Weights")
        st.dataframe(res["weights"], use_container_width=True, hide_index=True)
    with cwb:
        st.subheader("Portfolio Metrics")
        st.dataframe(res["metrics"], use_container_width=True)

    st.subheader("Charts")
    ftabs = st.tabs(["Monte Carlo", "Monte Carlo Distribution",
                     "Backtest", "Rate Hike Stress"])
    for ftab, key in zip(ftabs, ["monte_carlo", "monte_carlo_dist",
                                 "backtest", "rate_hike"]):
        with ftab:
            show_fig(res["figs"][key],
                     caption="No chart — none of the held ETFs traded through the "
                             "2022 rate-hike window.")

    section(3, "Save This Portfolio", optional=True)
    name = st.text_input("Portfolio name", placeholder="e.g. My cash sleeve",
                         key="custom_save_name")
    if st.button("Save Portfolio"):
        chart_labels = {"monte_carlo": "Monte Carlo", "backtest": "Backtest",
                        "rate_hike": "Rate Hike Stress"}
        charts = {lbl: res["figs"].get(k) for k, lbl in chart_labels.items()}
        save_portfolio(
            name, "custom", inputs,
            {"weights": res["weights"], "metrics": res["metrics"]},
            meta={"window": [str(start), str(end)], "dropped": res["dropped"],
                  "summary": ", ".join(inputs["weights"].keys())},
            charts=charts,
        )
        st.success("Saved! Find it on the Home page under **Saved Portfolios**.")
