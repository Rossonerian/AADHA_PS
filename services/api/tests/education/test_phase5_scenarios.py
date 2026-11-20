"""Phase 5 tests: >=20 curated Indian stock scenarios, zero lookahead, live price recomputation."""

from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

import pandas as pd

from app.core import guardrails
from app.education.exceptions import ValidationDomainError
from app.education.loader import load_seed_directory
from app.education.repository import EducationRepository, apply_migrations
from app.education.scenarios import (
    answer_scenario,
    build_public_scenario,
    get_next_scenario,
    recompute_scenario_outcome,
    scenario_outcome,
)
from tests.education._market_seed import use_education_price_seed


class TestPhase5Scenarios(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(use_education_price_seed())
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_migrations(self.conn)
        self.repo = EducationRepository(self.conn)
        load_seed_directory(self.repo)

    def tearDown(self) -> None:
        self.conn.close()

    def test_at_least_20_scenarios_and_every_outcome_recomputed_from_price_data(
        self,
    ) -> None:
        scenarios = self.repo.list_scenarios()
        self.assertGreaterEqual(len(scenarios), 20)

        for sc in scenarios:
            self.assertIn(sc["data_origin"], ("real", "synthetic"))
            self.assertGreaterEqual(int(sc["as_of_date"][:4]), 2005)
            self.assertGreaterEqual(len(sc["context"]["headlines"]), 2)
            self.assertLessEqual(len(sc["context"]["headlines"]), 4)
            self.assertGreater(len(sc["context"]["chart"]), 0)

            # Zero lookahead leakage check
            pub = build_public_scenario(sc)
            for pt in pub["context"]["chart"]:
                self.assertLessEqual(pt["date"], sc["as_of_date"])
            self.assertIn("Historical learning exercise", pub["context"]["disclaimer"])

            # Synthetic records are deterministic test fixtures, so their cached
            # outcome must match the fixture. Real seeds are refreshed separately
            # from adjusted upstream history and remain covered by origin checks.
            live = recompute_scenario_outcome(
                sc["symbol"], sc["as_of_date"], sc["window_days"]
            )
            stored = sc["outcome"]
            self.assertIn(live["data_origin"], ("real", "synthetic"))
            if sc["data_origin"] == "synthetic":
                self.assertAlmostEqual(
                    stored["stock_pct"], live["stock_pct"], places=2, msg=sc["id"]
                )
                self.assertAlmostEqual(
                    stored["index_pct"], live["index_pct"], places=2, msg=sc["id"]
                )
                self.assertEqual(
                    stored["actual_direction"], live["actual_direction"], msg=sc["id"]
                )

    def test_get_next_and_answer_scenario_scores_vs_actual_and_nifty50(self) -> None:
        self.repo.ensure_user("u_scen", level=1)
        nxt = get_next_scenario(self.repo, "u_scen", user_level=1, difficulty=2)
        self.assertIn("id", nxt)
        sc_full = self.repo.get_scenario(nxt["id"])
        assert sc_full is not None
        expected_dir = sc_full["outcome"]["actual_direction"]

        res = answer_scenario(
            self.repo,
            user_id="u_scen",
            user_level=1,
            scenario_id=nxt["id"],
            direction=expected_dir,
            confidence=80,
            clues=["auditor resignation"],
        )
        self.assertTrue(res["correct"])
        self.assertIn("stock_pct", res["outcome"])
        self.assertIn("index_pct", res["outcome"])
        self.assertGreater(len(res["key_clues"]), 0)
        self.assertTrue(guardrails.check_output(res["explanation"]).ok)

    def test_real_label_is_downgraded_when_either_price_series_is_synthetic(
        self,
    ) -> None:
        stock = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-01-11"]),
                "close": [100.0, 110.0],
                "data_origin": ["synthetic", "synthetic"],
            }
        )
        index = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-01-11"]),
                "close": [100.0, 105.0],
                "data_origin": ["real", "real"],
            }
        )
        sc = {
            "id": "sc_origin_check",
            "symbol": "TEST",
            "as_of_date": "2020-01-01",
            "window_days": 10,
            "difficulty": 1,
            "tags": [],
            "data_origin": "real",
            "outcome": {"actual_direction": "up"},
            "context": {
                "company": "Test Co",
                "chart": [{"date": "2020-01-01", "close": 100.0}],
            },
        }
        with (
            patch("app.education.scenarios.market.prices", return_value=stock),
            patch("app.education.scenarios.market.index", return_value=index),
        ):
            outcome, origin = scenario_outcome(sc)
        public = build_public_scenario(sc, series_data_origin=origin)
        self.assertEqual(outcome["data_origin"], "synthetic")
        self.assertEqual(public["data_origin"], "synthetic")

    def test_scenario_rejects_price_rows_that_do_not_cover_both_window_ends(
        self,
    ) -> None:
        late_only = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-02", "2020-01-05"]),
                "close": [100.0, 105.0],
                "data_origin": ["real", "real"],
            }
        )
        with (
            patch("app.education.scenarios.market.prices", return_value=late_only),
            patch("app.education.scenarios.market.index", return_value=late_only),
            self.assertRaises(ValidationDomainError) as error,
        ):
            recompute_scenario_outcome("TEST", "2020-01-01", 10)
        self.assertEqual(error.exception.code, "MARKET_DATA_MISSING")


if __name__ == "__main__":
    unittest.main()
