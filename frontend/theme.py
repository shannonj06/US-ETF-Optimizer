"""Shared InvestMint branding for the Streamlit frontend.

Import and call `apply_theme(...)` at the very top of every page (before any
other Streamlit command). It sets the page config, loads the brand font,
injects the brand CSS, and draws the InvestMint header with the mint-leaf mark.

IMPORTANT: every HTML/CSS string passed to st.markdown is dedented and stripped.
Streamlit renders markdown, and any line indented 4+ spaces becomes a literal
code block — which is why raw HTML tags can show up on the page. Keep injected
strings flush-left.
"""
from textwrap import dedent
import streamlit as st

COLORS = {
    "mint": "#16C79A",        # primary brand accent
    "mint_dark": "#0FA982",   # hover / pressed
    "mint_soft": "#E8F8F2",   # tinted fills
    "navy": "#16324F",        # headings (refined navy, not harsh black)
    "ink": "#3D4D5C",         # body text — softer than black
    "slate": "#6B7A89",       # secondary / captions
    "bg": "#FBFDFC",
    "panel": "#FFFFFF",
    "border": "#E6EDEA",
}

# Mint-leaf logo mark: a soft mint gradient tile with a white leaf + center vein.
_LOGO_SVG = dedent("""
<svg width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="imLeaf" x1="0" y1="0" x2="46" y2="46" gradientUnits="userSpaceOnUse">
      <stop stop-color="#21D9A6"/>
      <stop offset="1" stop-color="#0FA982"/>
    </linearGradient>
  </defs>
  <rect width="46" height="46" rx="13" fill="url(#imLeaf)"/>
  <path d="M34 11C20 11 12 19 12 31c0 1 0 2 .2 3 11 1 21-7 22-19 0-1.4-.1-2.7-.2-4z" fill="#FFFFFF"/>
  <path d="M14 33C20 27 26 21 32 15" stroke="#0FA982" stroke-width="2" stroke-linecap="round"/>
</svg>
""").strip()


def _inject_css():
    c = COLORS
    # Load the font via <link> too — @import inside an injected <style> is
    # sometimes dropped, the link tag is reliable.
    st.markdown(
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link href='https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap' rel='stylesheet'>",
        unsafe_allow_html=True,
    )
    css = dedent(f"""
    <style>
    html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select,
    [data-testid="stDataFrame"] {{
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }}

    .stApp {{ background: {c['bg']}; color: {c['ink']}; }}
    .block-container {{ padding-top: 1.2rem; max-width: 1480px; }}

    /* Typography — refined, not heavy-black */
    h1 {{ color: {c['navy']} !important; font-weight: 700 !important; letter-spacing: -0.6px; }}
    h2, h3, h4 {{ color: {c['navy']} !important; font-weight: 600 !important; letter-spacing: -0.3px; }}
    p, li, label, .stMarkdown {{ color: {c['ink']}; font-size: 0.95rem; line-height: 1.55; }}
    [data-testid="stCaptionContainer"], .stCaption, .stCaption p {{ color: {c['slate']} !important; font-size: 0.85rem !important; }}
    [data-testid="stWidgetLabel"] label p {{ color: {c['navy']} !important; font-weight: 600; }}

    /* Brand header */
    .im-header {{
        display: flex; align-items: center; gap: 16px;
        padding: 18px 22px; margin-bottom: 24px;
        background: linear-gradient(135deg, #FFFFFF 0%, {c['mint_soft']} 100%);
        border: 1px solid {c['border']};
        border-radius: 18px;
        box-shadow: 0 6px 22px rgba(11, 37, 64, 0.06);
    }}
    .im-title {{ font-size: 1.55rem; font-weight: 800; color: {c['navy']}; line-height: 1.05; letter-spacing: -0.6px; }}
    .im-title b {{ color: {c['mint']}; font-weight: 800; }}
    .im-sub {{ font-size: 0.88rem; color: {c['slate']}; margin-top: 3px; font-weight: 500; }}

    /* Numbered step header (replaces the giant st.header lines) */
    .im-step {{ display: flex; align-items: center; gap: 13px; margin: 26px 0 4px; }}
    .im-step-num {{
        flex: 0 0 auto; width: 30px; height: 30px; border-radius: 9px;
        background: linear-gradient(135deg, {c['mint']}, {c['mint_dark']});
        color: #fff; font-weight: 700; font-size: 0.95rem;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 3px 10px rgba(22, 199, 154, 0.30);
    }}
    .im-step-title {{ font-size: 1.12rem; font-weight: 700; color: {c['navy']}; letter-spacing: -0.3px; }}
    .im-pill {{
        margin-left: 9px; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.4px;
        text-transform: uppercase; color: {c['slate']}; background: {c['mint_soft']};
        padding: 3px 8px; border-radius: 999px; vertical-align: middle;
    }}

    /* Buttons */
    .stButton > button {{
        background: linear-gradient(135deg, {c['mint']}, {c['mint_dark']});
        color: #fff !important; border: none; border-radius: 11px;
        font-weight: 700; padding: 0.5rem 1.3rem;
        box-shadow: 0 4px 14px rgba(22, 199, 154, 0.28);
        transition: transform .12s ease, box-shadow .12s ease;
    }}
    .stButton > button:hover {{ transform: translateY(-1px); box-shadow: 0 6px 18px rgba(22, 199, 154, 0.40); }}
    .stButton > button p {{ color: #fff !important; font-weight: 700; }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid {c['border']}; }}
    .stTabs [data-baseweb="tab"] {{ border-radius: 11px 11px 0 0; padding: 9px 18px; font-weight: 600; color: {c['slate']}; }}
    .stTabs [aria-selected="true"] {{ background: {c['mint_soft']} !important; color: {c['navy']} !important; box-shadow: inset 0 -3px 0 {c['mint']}; }}

    /* Inputs & expanders */
    [data-testid="stExpander"] {{ border: 1px solid {c['border']}; border-radius: 14px; box-shadow: 0 2px 10px rgba(11,37,64,0.03); }}
    [data-testid="stExpander"] summary {{ font-weight: 600; color: {c['navy']}; }}
    [data-baseweb="select"] > div, .stNumberInput input, .stTextInput input {{
        border-radius: 10px !important; border-color: {c['border']} !important;
    }}
    [data-baseweb="select"] > div:focus-within, .stNumberInput input:focus, .stTextInput input:focus {{
        border-color: {c['mint']} !important; box-shadow: 0 0 0 2px {c['mint_soft']} !important;
    }}

    /* Dataframes — clean tech-table look */
    [data-testid="stDataFrame"] {{
        border: 1px solid {c['border']}; border-radius: 14px; overflow: hidden;
        box-shadow: 0 4px 16px rgba(11, 37, 64, 0.05);
    }}
    [data-testid="stDataFrame"] [class*="glideDataEditor"] {{ --gdg-bg-header: {c['mint_soft']}; }}
    [data-testid="stDataFrame"] thead tr th {{
        background: {c['mint_soft']} !important; color: {c['navy']} !important;
        font-weight: 700 !important; border-bottom: 1px solid {c['border']} !important;
    }}
    [data-testid="stDataFrame"] tbody tr:nth-child(even) {{ background: {c['bg']} !important; }}
    [data-testid="stDataFrame"] tbody tr:hover {{ background: {c['mint_soft']} !important; }}

    .im-card-title {{
        font-weight: 700; color: {c['navy']}; font-size: 0.98rem; text-align: center;
        margin-bottom: 10px; padding: 7px 0; background: {c['mint_soft']}; border-radius: 9px;
    }}

    /* Hide Streamlit's auto file-based sidebar nav — the app is driven by the
       landing-page cards and in-page links instead. */
    [data-testid="stSidebarNav"] {{ display: none; }}

    /* Choice cards on the landing page */
    .im-choice {{
        border: 1px solid {c['border']}; border-radius: 16px; padding: 16px 18px 14px;
        background: linear-gradient(135deg, #FFFFFF 0%, {c['mint_soft']} 140%);
        box-shadow: 0 6px 22px rgba(11, 37, 64, 0.06); margin-bottom: 10px;
    }}
    .im-choice-title {{ font-size: 1.12rem; font-weight: 800; color: {c['navy']}; margin: 0 0 5px; letter-spacing: -0.3px; }}
    .im-choice-desc {{ font-size: 0.88rem; color: {c['slate']}; line-height: 1.45; }}

    /* Ticker rows on the input builder */
    .im-rownum {{
        width: 26px; height: 26px; border-radius: 8px; margin-top: 4px;
        background: {c['mint_soft']}; color: {c['navy']}; font-weight: 700; font-size: 0.8rem;
        display: flex; align-items: center; justify-content: center;
    }}

    /* Page links */
    [data-testid="stPageLink"] a {{ color: {c['mint_dark']} !important; font-weight: 600; }}
    [data-testid="stPageLink"] a:hover {{ color: {c['mint']} !important; }}
    </style>
    """).strip()
    st.markdown(css, unsafe_allow_html=True)


def section(number, title, optional=False):
    """Render a clean numbered step header (replaces big st.header lines)."""
    pill = "<span class='im-pill'>Optional</span>" if optional else ""
    st.markdown(
        f"<div class='im-step'>"
        f"<div class='im-step-num'>{number}</div>"
        f"<div class='im-step-title'>{title}{pill}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def apply_theme(page_title="InvestMint", subtitle=None, layout="wide"):
    """Set page config, load font + CSS, and render the brand header. Call first."""
    st.set_page_config(page_title=f"InvestMint · {page_title}",
                       page_icon="🌿", layout=layout,
                       initial_sidebar_state="collapsed")
    _inject_css()
    sub = f"<div class='im-sub'>{subtitle}</div>" if subtitle else ""
    header = dedent(f"""
    <div class="im-header">
    {_LOGO_SVG}
    <div>
    <div class="im-title">Invest<b>Mint</b></div>
    {sub}
    </div>
    </div>
    """).strip()
    st.markdown(header, unsafe_allow_html=True)


def show_fig(fig, caption=None):
    """Render a matplotlib figure consistently, or a note if it's missing.

    Some figs (e.g. rate_hike when the lookback doesn't reach the stress
    window) come back as None — st.pyplot(None) errors, so we skip those.
    """
    if fig is None:
        st.caption(caption or "No chart — not enough data for this window.")
        return
    try:
        fig.patch.set_facecolor("white")
        fig.tight_layout()
    except Exception:
        pass
    st.pyplot(fig, use_container_width=True)
