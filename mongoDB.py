"""Refresh the MongoDB ETF universe from Yahoo Finance.

Run weekly by .github/workflows/update.yml, unattended.

Why this is more than delete + insert
-------------------------------------
This script used to call ``delete_many({})`` and then ``insert_many(...)``
directly. ``update()`` only raises when *every* ticker fails, so a partial
Yahoo outage - rate limiting, a bad session, a network blip - produced a small
but non-empty frame, and the collection was replaced with it. The app has no
US CSV fallback, so a run that returned 30 of 400 tickers silently shrank the
screening universe until someone noticed portfolios looked wrong.

So a refresh now has to clear three gates before anything is deleted:

1. **Shape** - every expected column present, no duplicate or blank symbols,
   and the columns the screener filters on carry real values.
2. **Volume** - at least ``--min-rows`` rows, and no more than ``--max-shrink``
   smaller than what is already in the collection.
3. **Recoverability** - the current collection is snapshotted to a local JSON
   file *and* to a backup collection before the swap, and restored
   automatically if the insert fails partway.

Any failure exits non-zero so the GitHub Action goes red instead of reporting
success over a damaged collection.

Usage
-----
    python mongoDB.py                 # refresh, with all guards active
    python mongoDB.py --dry-run       # fetch + validate only, touch nothing
    python mongoDB.py --force         # bypass the shrink guard (intentional
                                      # universe reductions only)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import certifi
import pandas as pd
from pymongo import MongoClient

from configuration import MONGODB_URL
from update import OUTPUT_COLS, update

BASE = Path(__file__).resolve().parent
BACKUP_DIR = BASE / "data_sourcing" / "backups"

DB_NAME = "etf_data"
COLLECTION_NAME = "US_ETF_DATA"
BACKUP_COLLECTION_NAME = f"{COLLECTION_NAME}_backup"

# A refresh smaller than this is treated as a failed fetch, not a real universe.
DEFAULT_MIN_ROWS = 100

# Reject a refresh that loses more than this fraction of the existing rows.
DEFAULT_MAX_SHRINK = 0.10

# Columns the screener filters on. If one of these is entirely empty the fetch
# came back structurally broken even though rows exist.
CRITICAL_COLUMNS = ["Symbol", "AUM", "YIELD", "SHARPE"]

# A column may be this sparse before the refresh is rejected. DURATION and ER
# are legitimately missing for many equity ETFs, so they are not critical above.
MAX_NULL_FRACTION = 0.50


class RefreshAborted(RuntimeError):
    """A guard rejected the refresh. Nothing was written."""


# -- Validation --------------------------------------------------------------
def validate_frame(df: pd.DataFrame, min_rows: int) -> list[str]:
    """Structural checks on a freshly fetched universe.

    Returns a list of human-readable problems; empty means the frame is usable.
    """
    problems: list[str] = []

    if df is None or df.empty:
        return ["The refresh returned no rows at all."]

    missing_cols = [c for c in OUTPUT_COLS if c not in df.columns]
    if missing_cols:
        problems.append(f"Missing expected column(s): {', '.join(missing_cols)}.")

    if len(df) < min_rows:
        problems.append(
            f"Only {len(df)} rows were fetched; at least {min_rows} are required. "
            "This usually means Yahoo Finance rate-limited the run."
        )

    if "Symbol" in df.columns:
        symbols = df["Symbol"].astype(str).str.strip()
        blank = int((symbols == "").sum() + df["Symbol"].isna().sum())
        if blank:
            problems.append(f"{blank} row(s) have a blank Symbol.")
        duplicated = symbols[symbols.duplicated()].unique().tolist()
        if duplicated:
            preview = ", ".join(duplicated[:5])
            more = f" (+{len(duplicated) - 5} more)" if len(duplicated) > 5 else ""
            problems.append(f"Duplicate symbol(s): {preview}{more}.")

    for column in CRITICAL_COLUMNS:
        if column not in df.columns:
            continue
        null_fraction = float(df[column].isna().mean())
        if null_fraction > MAX_NULL_FRACTION:
            problems.append(
                f"Column '{column}' is {null_fraction:.0%} empty "
                f"(limit {MAX_NULL_FRACTION:.0%}); the fetch looks broken."
            )

    return problems


def check_shrink(new_rows: int, existing_rows: int, max_shrink: float) -> str | None:
    """Reject a refresh that loses too much of the existing universe."""
    if existing_rows == 0:
        return None  # first load: nothing to compare against
    floor = int(existing_rows * (1 - max_shrink))
    if new_rows < floor:
        lost = existing_rows - new_rows
        return (
            f"The refresh has {new_rows} rows but the collection currently holds "
            f"{existing_rows} - that drops {lost} ETFs "
            f"({lost / existing_rows:.0%}), past the {max_shrink:.0%} limit. "
            "Re-run once Yahoo Finance is responding, or pass --force if the "
            "universe really did shrink."
        )
    return None


# -- Backup / restore --------------------------------------------------------
def snapshot_to_file(documents: list[dict]) -> Path | None:
    """Write the pre-refresh collection to a timestamped JSON file.

    The GitHub Action uploads this as an artifact, so a bad run is recoverable
    even if the backup collection is also lost.
    """
    if not documents:
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    path = BACKUP_DIR / f"{COLLECTION_NAME}.{stamp}.json"
    path.write_text(
        json.dumps(documents, indent=2, default=str), encoding="utf-8"
    )
    return path


def snapshot_to_collection(db, documents: list[dict]) -> None:
    """Mirror the pre-refresh documents into the backup collection."""
    if not documents:
        return
    backup = db[BACKUP_COLLECTION_NAME]
    backup.delete_many({})
    backup.insert_many(documents)


def restore(collection, documents: list[dict]) -> None:
    """Put the previous documents back after a failed swap."""
    if not documents:
        return
    collection.delete_many({})
    collection.insert_many(documents)


# -- Main --------------------------------------------------------------------
def refresh(dry_run: bool = False, force: bool = False,
            min_rows: int = DEFAULT_MIN_ROWS,
            max_shrink: float = DEFAULT_MAX_SHRINK) -> int:
    """Fetch, validate and (unless dry-run) swap in the new universe.

    Returns the number of rows written (0 for a dry run).
    """
    print("Fetching the refreshed ETF universe...")
    df = update(write=False)

    problems = validate_frame(df, min_rows)
    if problems:
        raise RefreshAborted(
            "The fetched universe failed validation:\n  - "
            + "\n  - ".join(problems)
        )
    df = df[OUTPUT_COLS]
    print(f"Fetched and validated {len(df)} rows.")

    if not MONGODB_URL:
        raise RefreshAborted(
            "MONGODB_URL is not set. In CI it comes from the MONGODB_URL "
            "repository secret; locally it comes from the .env file."
        )

    client = MongoClient(MONGODB_URL, tlsCAFile=certifi.where())
    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        existing = list(collection.find({}))
        existing_rows = len(existing)
        print(f"The collection currently holds {existing_rows} rows.")

        shrink_problem = check_shrink(len(df), existing_rows, max_shrink)
        if shrink_problem:
            if force:
                print(f"WARNING (--force, continuing anyway): {shrink_problem}")
            else:
                raise RefreshAborted(shrink_problem)

        if dry_run:
            print("--dry-run: validation passed, the collection was not modified.")
            return 0

        backup_path = snapshot_to_file(existing)
        if backup_path:
            print(f"Backed up {existing_rows} rows -> {backup_path.name}")
        snapshot_to_collection(db, existing)

        records = df.to_dict("records")
        try:
            collection.delete_many({})
            collection.insert_many(records)
        except Exception as exc:
            print(f"ERROR: the swap failed ({exc}). Restoring the previous rows...")
            try:
                restore(collection, existing)
                print(f"Restored {existing_rows} rows.")
            except Exception as restore_exc:  # pragma: no cover - last resort
                print(
                    "CRITICAL: the restore also failed "
                    f"({restore_exc}). Recover from {backup_path} or the "
                    f"'{BACKUP_COLLECTION_NAME}' collection."
                )
            raise

        written = collection.count_documents({})
        if written != len(records):
            restore(collection, existing)
            raise RefreshAborted(
                f"Wrote {written} rows but expected {len(records)}; "
                "the previous rows have been restored."
            )

        print(f"Success: the collection now holds {written} rows.")
        return written
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and validate without modifying the collection.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass the shrink guard (for a genuine universe reduction).",
    )
    parser.add_argument(
        "--min-rows", type=int, default=DEFAULT_MIN_ROWS,
        help=f"Reject a refresh with fewer rows than this (default {DEFAULT_MIN_ROWS}).",
    )
    parser.add_argument(
        "--max-shrink", type=float, default=DEFAULT_MAX_SHRINK,
        help=(
            "Reject a refresh that loses more than this fraction of the existing "
            f"rows (default {DEFAULT_MAX_SHRINK})."
        ),
    )
    args = parser.parse_args(argv)

    try:
        refresh(
            dry_run=args.dry_run,
            force=args.force,
            min_rows=args.min_rows,
            max_shrink=args.max_shrink,
        )
    except RefreshAborted as exc:
        print(f"\nREFRESH ABORTED - the collection was not modified.\n{exc}",
              file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\nREFRESH FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
