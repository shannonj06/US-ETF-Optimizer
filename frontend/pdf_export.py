"""Build a one-click PDF report for a saved portfolio.

Uses only matplotlib (already a dependency) via its PDF backend — no reportlab /
fpdf needed. The report has a cover page, the holdings + metrics tables, and the
important graphs that were captured when the portfolio was saved.
"""
import base64
import io

from storage import obj_to_df

NAVY = "#16324F"
MINT_SOFT = "#E8F8F2"
SLATE = "#6B7A89"

# Full-portfolio tables to render per optimizer, in order.
_OPT_TABLES = [
    ("SLSQP — Weights", "slsqp", True),
    ("SLSQP — Metrics", "slsqp_metrics", False),
    ("CVXPY — Weights", "cvxpy", True),
    ("CVXPY — Metrics", "cvxpy_metrics", False),
    ("HRP — Weights", "hrp", True),
    ("HRP — Metrics", "hrp_metrics", False),
]


def _weights_for_display(df):
    """ETF / Weight(float) -> ETF / Weight(%) string table."""
    out = df.copy()
    if "Weight" in out.columns:
        out["Weight"] = (out["Weight"] * 100).map(lambda x: f"{x:.2f}%")
    return out


def _draw_table(ax, title, df, is_metrics):
    ax.axis("off")
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left",
                 color=NAVY, pad=6)
    if is_metrics:
        col_labels = ["Metric", df.columns[0] if len(df.columns) else "Value"]
        cell_text = [[str(idx), str(row.iloc[0])] for idx, row in df.iterrows()]
    else:
        col_labels = list(df.columns)
        cell_text = df.astype(str).values.tolist()
    if not cell_text:
        return
    tbl = ax.table(cellText=cell_text, colLabels=col_labels,
                   loc="upper left", cellLoc="left", colLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    tbl.scale(1, 1.35)
    for (r, _c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#E6EDEA")
        if r == 0:
            cell.set_facecolor(MINT_SOFT)
            cell.set_text_props(color=NAVY, fontweight="bold")


def _table_pages(pdf, plt, title_blocks):
    """Render (title, df, is_metrics) blocks two per portrait page."""
    for i in range(0, len(title_blocks), 2):
        chunk = title_blocks[i:i + 2]
        fig, axes = plt.subplots(2, 1, figsize=(8.5, 11))
        fig.subplots_adjust(left=0.07, right=0.93, top=0.94, bottom=0.05, hspace=0.25)
        for ax, (title, df, is_metrics) in zip(axes, chunk):
            _draw_table(ax, title, df, is_metrics)
        for ax in axes[len(chunk):]:
            ax.axis("off")
        pdf.savefig(fig)
        plt.close(fig)


def build_pdf(record: dict) -> bytes:
    """Return the report PDF for one saved-portfolio record as bytes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    tables = record.get("tables", {})
    charts = record.get("charts", {})
    meta = record.get("meta", {})

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # ── Cover ───────────────────────────────────────────────────────────
        cover = plt.figure(figsize=(8.5, 11))
        cover.text(0.07, 0.88, "InvestMint", fontsize=26, fontweight="bold", color=NAVY)
        cover.text(0.07, 0.83, "Portfolio Report", fontsize=14, color=SLATE)
        kind = "Optimization" if record.get("type") == "optimization" else "Custom (your holdings)"
        lines = [
            f"Name:     {record.get('name', '')}",
            f"Type:     {kind}",
            f"Created:  {record.get('created', '')}",
        ]
        if meta.get("summary"):
            lines.append(f"Holdings: {meta['summary']}")
        if meta.get("window"):
            w = meta["window"]
            lines.append(f"Window:   {w[0]} → {w[1]}")
        if record.get("inputs", {}).get("rf") is not None:
            lines.append(f"Risk-free rate: {record['inputs']['rf']:.2%}")
        cover.text(0.07, 0.74, "\n".join(lines), fontsize=11, color=NAVY,
                   va="top", family="monospace", linespacing=1.8)
        pdf.savefig(cover)
        plt.close(cover)

        # ── Tables ──────────────────────────────────────────────────────────
        blocks = []
        if record.get("type") == "optimization":
            for title, key, is_w in _OPT_TABLES:
                if key in tables:
                    df = obj_to_df(tables[key])
                    blocks.append((title, _weights_for_display(df) if is_w else df, not is_w))
        else:
            if "weights" in tables:
                blocks.append(("Holdings", _weights_for_display(obj_to_df(tables["weights"])), False))
            if "metrics" in tables:
                blocks.append(("Portfolio Metrics", obj_to_df(tables["metrics"]), True))
        _table_pages(pdf, plt, blocks)

        # ── Charts (one per page) ─────────────────────────────────────────────
        for label, b64 in charts.items():
            img = mpimg.imread(io.BytesIO(base64.b64decode(b64)), format="png")
            fig = plt.figure(figsize=(8.5, 11))
            ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
            ax.imshow(img)
            ax.axis("off")
            ax.set_title(label, fontsize=12, fontweight="bold", color=NAVY)
            pdf.savefig(fig)
            plt.close(fig)

    return buf.getvalue()
