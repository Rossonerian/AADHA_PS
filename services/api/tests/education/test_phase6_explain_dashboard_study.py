"""Phase 6 tests: 30 Explain-a-Stock records with cited sources, Dashboard, Study Mode, 95% CI Export."""
from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.api.app.core import guardrails, market
from services.api.app.education.exceptions import ToolLockedError
from services.api.app.education.explain import (
    explain_stock,
    get_dashboard,
    start_study_session,
    submit_study_session,
)
from services.api.app.education.loader import load_seed_directory
from services.api.app.education.repository import EducationRepository, apply_migrations
from services.api.app.education.scenarios import recompute_scenario_outcome
from services.api.app.education.scripts.export_evidence import export_evidence_files


class TestPhase6ExplainDashboardStudy(unittest.TestCase):
    def setUp(self) -> None:
        market.load_price_store()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_migrations(self.conn)
        self.repo = EducationRepository(self.conn)
        load_seed_directory(self.repo)

    def tearDown(self) -> None:
        self.conn.close()

    def test_all_30_explain_stocks_have_sourced_events_and_pass_guardrails(self) -> None:
        recs = self.repo.list_explain_records()
        self.assertGreaterEqual(len(recs), 30)

        # Level 1 user must be blocked with 403 TOOL_LOCKED
        self.repo.ensure_user("u_exp_l1", level=1)
        with self.assertRaises(ToolLockedError) as ctx:
            explain_stock(self.repo, "u_exp_l1", 1, "PAYTM", 2021)
        self.assertEqual(ctx.exception.required_level, 2)

        # Level 2 user can access all 30 stocks (including fuzzy alias resolution)
        self.repo.ensure_user("u_exp_l2", level=2)
        fuzzy = explain_stock(self.repo, "u_exp_l2", 2, "Paytm", 2021)
        self.assertEqual(fuzzy["symbol"], "PAYTM")

        for r in recs:
            res = explain_stock(self.repo, "u_exp_l2", 2, r["symbol"], r["year"])
            self.assertGreater(len(res["chart"]), 0)
            self.assertGreater(len(res["moves"]), 0)
            self.assertTrue(guardrails.check_output(res["summary"]).ok)
            for mv in res["moves"]:
                self.assertGreater(len(mv["events"]), 0)
                for ev in mv["events"]:
                    self.assertTrue(ev["source"].strip(), f"Missing source in {r['symbol']} {r['year']}")

    def test_dashboard_requires_level_4_and_returns_time_series(self) -> None:
        self.repo.ensure_user("u_dash_l3", level=3)
        with self.assertRaises(ToolLockedError) as ctx:
            get_dashboard(self.repo, "u_dash_l3", 3)
        self.assertEqual(ctx.exception.required_level, 4)

        self.repo.ensure_user("u_dash_l4", level=4)
        self.repo.record_skill_scores(
            "u_dash_l4",
            {"basics": 75.0, "reading_stock": 80.0, "judging_info": 85.0, "risk": 90.0},
            brier=0.14,
            measured_at="2026-11-19T10:00:00Z",
        )
        self.repo.record_attempt("u_dash_l4", "scenario", "sc_satyam_2009", "down", 85, True, "practice")
        dash = get_dashboard(self.repo, "u_dash_l4", 4)
        self.assertEqual(dash["level"], 4)
        self.assertEqual(len(dash["skills_over_time"]), 1)
        self.assertEqual(len(dash["brier_over_time"]), 1)
        self.assertEqual(dash["scenario_accuracy"][0]["accuracy_pct"], 100.0)

    def test_study_pre_and_post_use_disjoint_unseen_items(self) -> None:
        self.repo.ensure_user("u_study_live", level=1)
        pre = start_study_session(self.repo, "u_study_live", "study_pre")
        pre_ids = {i["item_id"] for i in pre["items"]}

        def answer_all(items, conf):
            out = []
            for item in items:
                if item["item_type"] == "question":
                    q = self.repo.get_question(item["item_id"])
                    assert q is not None
                    ans = q["answer"]
                else:
                    sc = self.repo.get_scenario(item["item_id"])
                    assert sc is not None
                    ans = recompute_scenario_outcome(sc["symbol"], sc["as_of_date"], sc["window_days"])["actual_direction"]
                out.append({"item_id": item["item_id"], "answer": ans, "confidence": conf})
            return out

        res_pre = submit_study_session(self.repo, "u_study_live", pre["session_id"], answer_all(pre["items"], 70))
        self.assertEqual(res_pre["context"], "study_pre")

        post = start_study_session(self.repo, "u_study_live", "study_post")
        post_ids = {i["item_id"] for i in post["items"]}
        self.assertEqual(len(pre_ids & post_ids), 0, "study_post must never reuse study_pre items")

        res_post = submit_study_session(self.repo, "u_study_live", post["session_id"], answer_all(post["items"], 85))
        self.assertEqual(res_post["context"], "study_post")

    def test_evidence_export_script_produces_csv_json_and_95_cis(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = export_evidence_files(self.repo, Path(td))
            self.assertTrue(out["csv"].exists())
            self.assertTrue(out["json"].exists())

            data = json.loads(out["json"].read_text(encoding="utf-8"))
            self.assertEqual(data["cohort_n"], 40)
            score_ci = data["metrics"]["score_pct"]["delta"]
            brier_ci = data["metrics"]["brier_score"]["delta"]
            rf_ci = data["metrics"]["red_flag_detection_pct"]["delta"]

            # Seeded cohort shows positive learning gain, lower (improved) Brier, higher red-flag detection
            self.assertGreater(score_ci["mean"], 0)
            self.assertLess(score_ci["ci_low"], score_ci["mean"])
            self.assertGreater(score_ci["ci_high"], score_ci["mean"])

            self.assertLess(brier_ci["mean"], 0)
            self.assertGreater(rf_ci["mean"], 0)

            with out["csv"].open("r", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 40)


if __name__ == "__main__":
    unittest.main()
