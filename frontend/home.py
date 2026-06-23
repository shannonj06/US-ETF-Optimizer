import sys
from pathlib import Path

# This file lives in US Optimization/frontend/, but it imports packages (config,
# scoring, Optimizer_Class, ...) that live in the project root one level up.
# `streamlit run` only puts THIS file's folder on sys.path, so add the root too.
# NOTE: this must run BEFORE importing build_portfolios / config / etc.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

import streamlit as st
from theme import apply_theme
from storage import load_portfolios, delete_portfolio, obj_to_df
from pdf_export import build_pdf

apply_theme("US Portfolio Optimizer",
            "Build an optimized portfolio, or evaluate one you already hold.")

tab_start, tab_saved = st.tabs(["Get Started", "Saved Portfolios"])

# ── Get Started: two paths ───────────────────────────────────────────────────
with tab_start:
    left, right = st.columns(2, gap="medium")

    with left:
        st.markdown(
            "<div class='im-choice'>"
            "<div class='im-choice-title'>Develop a Portfolio</div>"
            "<div class='im-choice-desc'>Screen the ETF universe, score it, and run "
            "the SLSQP / CVXPY / HRP optimizers to build a portfolio from scratch.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Develop a Portfolio", use_container_width=True, key="go_develop"):
            st.switch_page("pages/develop.py")

    with right:
        st.markdown(
            "<div class='im-choice'>"
            "<div class='im-choice-title'>Input Your Portfolio</div>"
            "<div class='im-choice-desc'>Already hold a set of ETFs? Enter your tickers "
            "and weights to get the same metrics and stress charts — no optimization.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Input Your Portfolio", use_container_width=True, key="go_custom"):
            st.switch_page("pages/custom.py")

# ── Saved Portfolios ─────────────────────────────────────────────────────────
def _show_optimization_tables(tables):
    """Saved optimizer run: one tab per method, each with weights + metrics."""
    methods = [("SLSQP", "slsqp"), ("CVXPY", "cvxpy"), ("HRP", "hrp")]
    present = [(lbl, pre) for lbl, pre in methods if pre in tables]
    if not present:
        return
    for tab, (_lbl, pre) in zip(st.tabs([lbl for lbl, _ in present]), present):
        with tab:
            if f"{pre}4" in tables:
                st.caption("Top 4 holdings")
                st.dataframe(obj_to_df(tables[f"{pre}4"]), hide_index=True,
                             use_container_width=True)
            st.caption("Total portfolio weights")
            st.dataframe(obj_to_df(tables[pre]), hide_index=True,
                         use_container_width=True)
            if f"{pre}_metrics" in tables:
                st.caption("Portfolio metrics")
                st.dataframe(obj_to_df(tables[f"{pre}_metrics"]),
                             use_container_width=True)


def _show_custom_tables(tables):
    cwa, cwb = st.columns(2)
    if "weights" in tables:
        with cwa:
            st.caption("Normalized weights")
            st.dataframe(obj_to_df(tables["weights"]), hide_index=True,
                         use_container_width=True)
    if "metrics" in tables:
        with cwb:
            st.caption("Portfolio metrics")
            st.dataframe(obj_to_df(tables["metrics"]), use_container_width=True)


with tab_saved:
    portfolios = load_portfolios()
    if not portfolios:
        st.info("No saved portfolios yet. Run an optimization or evaluate your own "
                "holdings, then use **Save Portfolio** to keep it here.")
    else:
        st.caption(f"{len(portfolios)} saved portfolio(s) — newest first.")
        for p in portfolios:
            kind = "Optimization" if p["type"] == "optimization" else "Custom"
            summary = p.get("meta", {}).get("summary", "")
            title = f"{p['name']}  ·  {kind}  ·  {p['created']}"
            with st.expander(title):
                if summary:
                    st.caption(summary)

                if p["type"] == "optimization":
                    _show_optimization_tables(p.get("tables", {}))
                else:
                    _show_custom_tables(p.get("tables", {}))

                a1, a2, a3, _ = st.columns([2, 2, 2, 4])
                if p["type"] == "custom":
                    with a1:
                        if st.button("Reopen in builder", key=f"open_{p['id']}"):
                            st.session_state["reopen_custom"] = p.get("inputs", {})
                            st.switch_page("pages/custom.py")
                with a2:
                    pdf_key = f"pdf_{p['id']}"
                    if pdf_key in st.session_state:
                        fname = re.sub(r"[^\w.-]+", "_", p["name"]).strip("_") or "portfolio"
                        st.download_button("Download PDF", data=st.session_state[pdf_key],
                                           file_name=f"{fname}.pdf", mime="application/pdf",
                                           key=f"dl_{p['id']}")
                    elif st.button("Export PDF", key=f"exp_{p['id']}"):
                        try:
                            st.session_state[pdf_key] = build_pdf(p)
                        except Exception as e:
                            st.error(f"Could not build PDF: {e}")
                        else:
                            st.rerun()
                with a3:
                    if st.button("Delete", key=f"del_{p['id']}"):
                        st.session_state.pop(f"pdf_{p['id']}", None)
                        delete_portfolio(p["id"])
                        st.rerun()
