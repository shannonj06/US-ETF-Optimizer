"""Guards that stop the weekly cron from replacing the universe with junk.

The failure this prevents: Yahoo Finance rate-limits the Monday run, ``update()``
returns 30 of ~400 tickers without raising (it only raises at zero), and the
collection is replaced with those 30. Nothing alerts, and the screener quietly
operates on a crippled universe until someone notices the portfolios look wrong.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import mongoDB
from update import OUTPUT_COLS


def make_universe(rows: int = 200, **overrides) -> pd.DataFrame:
    """A structurally valid refresh frame."""
    frame = pd.DataFrame({
        "Symbol":        [f"ET{i:04d}" for i in range(rows)],
        "BETA":          np.linspace(0.5, 1.5, rows),
        "Name":          [f"Test ETF {i}" for i in range(rows)],
        "AUM":           np.linspace(2e8, 9e10, rows),
        "YIELD":         np.linspace(0.01, 0.06, rows),
        "SHARPE":        np.linspace(0.1, 2.0, rows),
        "MAX_DD":        np.linspace(-0.4, -0.05, rows),
        "ANNUAL_VOL":    np.linspace(0.05, 0.3, rows),
        "STYLE":         ["equity"] * rows,
        "AVG_VOLUME_30": np.linspace(1e5, 1e7, rows),
        "DURATION":      [np.nan] * rows,
        "ER":            np.linspace(0.0003, 0.008, rows),
    })[OUTPUT_COLS]
    for column, value in overrides.items():
        frame[column] = value
    return frame


class TestValidateFrame:
    def test_a_healthy_refresh_passes(self):
        assert mongoDB.validate_frame(make_universe(), min_rows=100) == []

    def test_an_empty_refresh_is_rejected(self):
        problems = mongoDB.validate_frame(pd.DataFrame(), min_rows=100)
        assert problems and "no rows" in problems[0]

    def test_a_partial_fetch_is_rejected(self):
        """The exact rate-limiting scenario: a few tickers came back, not all."""
        problems = mongoDB.validate_frame(make_universe(rows=30), min_rows=100)
        assert any("at least 100" in p for p in problems)
        assert any("rate-limited" in p for p in problems)

    def test_a_missing_column_is_rejected(self):
        frame = make_universe().drop(columns=["YIELD"])
        problems = mongoDB.validate_frame(frame, min_rows=100)
        assert any("YIELD" in p for p in problems)

    def test_duplicate_symbols_are_rejected(self):
        frame = make_universe(rows=150)
        frame.loc[5, "Symbol"] = frame.loc[4, "Symbol"]
        problems = mongoDB.validate_frame(frame, min_rows=100)
        assert any("Duplicate symbol" in p for p in problems)

    def test_blank_symbols_are_rejected(self):
        frame = make_universe(rows=150)
        frame.loc[7, "Symbol"] = ""
        problems = mongoDB.validate_frame(frame, min_rows=100)
        assert any("blank Symbol" in p for p in problems)

    def test_a_critical_column_that_came_back_empty_is_rejected(self):
        """Rows exist but the metric the screener filters on is all null."""
        frame = make_universe(rows=200, AUM=np.nan)
        problems = mongoDB.validate_frame(frame, min_rows=100)
        assert any("'AUM'" in p for p in problems)

    def test_a_sparse_non_critical_column_is_tolerated(self):
        """DURATION is legitimately absent for most equity ETFs."""
        frame = make_universe(rows=200, DURATION=np.nan)
        assert mongoDB.validate_frame(frame, min_rows=100) == []


class TestShrinkGuard:
    def test_a_stable_refresh_is_allowed(self):
        assert mongoDB.check_shrink(398, 400, max_shrink=0.10) is None

    def test_a_growing_universe_is_allowed(self):
        assert mongoDB.check_shrink(450, 400, max_shrink=0.10) is None

    def test_a_shrink_inside_the_tolerance_is_allowed(self):
        assert mongoDB.check_shrink(365, 400, max_shrink=0.10) is None

    def test_a_large_shrink_is_rejected(self):
        problem = mongoDB.check_shrink(30, 400, max_shrink=0.10)
        assert problem is not None
        assert "30" in problem and "400" in problem
        assert "--force" in problem, "the message should name the override"

    def test_the_first_load_has_nothing_to_compare_against(self):
        assert mongoDB.check_shrink(200, 0, max_shrink=0.10) is None

    @pytest.mark.parametrize("new_rows,expected_ok", [
        (360, True),    # exactly at the 10% floor
        (359, False),   # one below it
    ])
    def test_the_boundary_is_where_it_is_documented(self, new_rows, expected_ok):
        problem = mongoDB.check_shrink(new_rows, 400, max_shrink=0.10)
        assert (problem is None) is expected_ok


class TestRefreshAbortsBeforeWriting:
    def test_a_failed_validation_never_reaches_the_database(self, monkeypatch):
        """The whole point: a bad fetch must not get as far as delete_many."""
        monkeypatch.setattr(mongoDB, "update", lambda market="US", write=False: make_universe(rows=20))

        def explode(*args, **kwargs):   # pragma: no cover - must not be reached
            raise AssertionError("MongoClient must not be constructed on a bad fetch")

        monkeypatch.setattr(mongoDB, "MongoClient", explode)

        with pytest.raises(mongoDB.RefreshAborted, match="failed validation"):
            mongoDB.refresh()

    def test_a_missing_connection_string_aborts(self, monkeypatch):
        monkeypatch.setattr(mongoDB, "update", lambda market="US", write=False: make_universe())
        monkeypatch.setattr(mongoDB, "MONGODB_URL", "")
        with pytest.raises(mongoDB.RefreshAborted, match="MONGODB_URL"):
            mongoDB.refresh()

    def test_main_returns_a_failing_exit_code_when_aborted(self, monkeypatch):
        """The GitHub Action has to go red, not report success."""
        monkeypatch.setattr(mongoDB, "update", lambda market="US", write=False: make_universe(rows=5))
        assert mongoDB.main([]) == 1


class TestMarketAwareness:
    """CA was added after this refresh script's original design (see
    CANADIAN_OPTIMIZER_BUILDOUT_BRIEF.md) -- these pin down the per-market
    behavior so a future change to MARKET_COLLECTIONS or the defaults doesn't
    silently regress it."""

    def test_an_unknown_market_is_rejected_before_any_fetch(self, monkeypatch):
        def explode(*args, **kwargs):   # pragma: no cover - must not be reached
            raise AssertionError("update() must not be called for an unknown market")

        monkeypatch.setattr(mongoDB, "update", explode)
        with pytest.raises(mongoDB.RefreshAborted, match="Unknown market"):
            mongoDB.refresh(market="EU")

    def test_default_min_rows_is_lower_for_the_smaller_ca_universe(self):
        assert mongoDB.default_min_rows("US") == 100
        assert mongoDB.default_min_rows("CA") == 80
        assert mongoDB.default_min_rows("XX") == 100  # unlisted markets fall back to the US default

    def test_a_ca_sized_refresh_would_fail_the_us_floor_but_passes_its_own(self):
        """187 rows (CA's real live count) is comfortably above CA's floor but
        would have tripped the old, US-only 100-row floor by a much thinner
        margin than it protects US with -- the scenario default_min_rows exists for."""
        frame = make_universe(rows=187)
        assert mongoDB.validate_frame(frame, min_rows=mongoDB.default_min_rows("CA")) == []

    def test_refresh_fetches_the_requested_market(self, monkeypatch):
        seen = {}

        def fake_update(market="US", write=False):
            seen["market"] = market
            return make_universe(rows=120)

        monkeypatch.setattr(mongoDB, "update", fake_update)
        monkeypatch.setattr(mongoDB, "MONGODB_URL", "")  # abort right after the fetch, before Mongo
        with pytest.raises(mongoDB.RefreshAborted, match="MONGODB_URL"):
            mongoDB.refresh(market="CA")
        assert seen["market"] == "CA"
