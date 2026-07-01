"""Tiny JSON-file store for saved portfolios.

Both flows — the optimizer and the custom-weights builder — save the inputs that
produced a portfolio plus a snapshot of its displayable tables. Saving the inputs
means a saved portfolio can be reopened/re-run later; the table snapshots let the
Saved tab show weights + metrics instantly without recomputing.

Figures (matplotlib) are NOT stored — they're regenerated on demand by re-running.
"""
import json
import uuid
from datetime import datetime 
from pathlib import Path

import pandas as pd

SAVE_PATH = Path(__file__).resolve().parent / "saved_portfolios.json"


def _df_to_obj(df: pd.DataFrame) -> dict:
    """Serialize a DataFrame (index + columns + data) to a JSON-safe dict."""
    return json.loads(df.to_json(orient="split"))


def _fig_to_b64(fig) -> str:
    """Render a matplotlib Figure to a base64 PNG so it can live in the JSON
    store — lets the PDF export embed graphs without recomputing them (an
    optimization re-run takes minutes)."""
    import base64
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor="white")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def obj_to_df(obj: dict) -> pd.DataFrame:
    """Inverse of _df_to_obj."""
    return pd.DataFrame(data=obj["data"], index=obj["index"], columns=obj["columns"])


def load_portfolios() -> list:
    """All saved portfolios, newest first. Returns [] if nothing saved yet."""
    if not SAVE_PATH.exists():
        return []
    try:
        return json.loads(SAVE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write(items: list) -> None:
    SAVE_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")


def save_portfolio(name: str, ptype: str, inputs: dict, tables: dict,
                   meta: dict = None, charts: dict = None) -> dict:
    """Append a portfolio record.

    name    : user-facing label.
    ptype   : "optimization" | "custom".
    inputs  : everything needed to re-run (JSON-serializable).
    tables  : {label: DataFrame} snapshot shown in the Saved tab.
    meta    : optional extra JSON-serializable info (window, dropped tickers, …).
    charts  : optional {label: matplotlib Figure}; stored as PNG for PDF export.
    """
    items = load_portfolios()
    chart_pngs = {}
    for label, fig in (charts or {}).items():
        if fig is not None:
            chart_pngs[label] = _fig_to_b64(fig)
    record = {
        "id": uuid.uuid4().hex[:8],
        "name": (name or "").strip() or f"{ptype.title()} portfolio",
        "type": ptype,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "inputs": inputs,
        "tables": {k: _df_to_obj(v) for k, v in tables.items()},
        "charts": chart_pngs,
        "meta": meta or {},
    }
    items.insert(0, record)
    _write(items)
    return record


def delete_portfolio(pid: str) -> None:
    _write([x for x in load_portfolios() if x.get("id") != pid])
