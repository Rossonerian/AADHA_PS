"""Phase 5 tests: >=20 curated Indian stock scenarios, zero lookahead, live price recomputation."""
from __future__ import annotations

import sqlite3
import unittest

from services.api.app.core import guardrails, market
from services.api.app.education.loader import load_seed_directory
from services.api.app.education.repository import EducationRepository, apply_migrations
from services.api.app.education.scenarios import (
    answer_scenario,
    build_public_scenario,
    get_next_scenario,
    recompute_scenario_outcome,
)


class TestPhase5Scenarios(unittest.TestCase):
    def setUp(self) -> None:
        market.load_price_store()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_migrations(self.conn)
        self.repo = EducationRepository(self.conn)
        load_seed_directory(self.repo)

    def tearDown(self) -> None:
        self.conn.close()

    def test_at_least_20_scenarios_and_every_outcome_recomputed_from_price_data(self) -> None:
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

            # CRITICAL Phase 5 "Done when" check: recompute from core.market and assert exact match
            live = recompute_scenario_outcome(sc["symbol"], sc["as_of_date"], sc["window_days"])
            stored = sc["outcome"]
            self.assertAlmostEqual(stored["stock_pct"], live["stock_pct"], places=2, msg=sc["id"])
            self.assertAlmostEqual(stored["index_pct"], live["index_pct"], places=2, msg=sc["id"])
            self.assertEqual(stored["actual_direction"], live["actual_direction"], msg=sc["id"])

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


if __name__ == "__main__":
    unittest.main()
