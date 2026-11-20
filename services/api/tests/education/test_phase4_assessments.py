"""Phase 4 tests: unseen items, pass/fail/calibration thresholds, level-up unlocks, fail->plan update."""
from __future__ import annotations

import sqlite3
import unittest

from services.api.app.core import market
from services.api.app.education.assessments import start_assessment, submit_assessment
from services.api.app.education.config import EducationConfig
from services.api.app.education.enums import AttemptContext, AttemptItemType
from services.api.app.education.exceptions import ValidationDomainError
from services.api.app.education.learning import get_plan, get_user_unlocks
from services.api.app.education.loader import load_seed_directory
from services.api.app.education.repository import EducationRepository, apply_migrations
from services.api.app.education.scenarios import recompute_scenario_outcome


class TestPhase4Assessments(unittest.TestCase):
    def setUp(self) -> None:
        market.load_price_store()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_migrations(self.conn)
        self.repo = EducationRepository(self.conn)
        load_seed_directory(self.repo)

    def tearDown(self) -> None:
        self.conn.close()

    def _build_answers(self, items, correct_count: int, confidence: int):
        answers = []
        for idx, item in enumerate(items):
            should_be_right = idx < correct_count
            if item["item_type"] == AttemptItemType.QUESTION.value:
                q = self.repo.get_question(item["item_id"])
                assert q is not None
                ans = q["answer"] if should_be_right else next(o for o in q["options"] if o != q["answer"])
            else:
                sc = self.repo.get_scenario(item["item_id"])
                assert sc is not None
                out = recompute_scenario_outcome(sc["symbol"], sc["as_of_date"], sc["window_days"])
                actual = out["actual_direction"]
                ans = actual if should_be_right else ("down" if actual == "up" else "up")
            answers.append({"item_id": item["item_id"], "answer": ans, "confidence": confidence})
        return answers

    def test_assessment_uses_unseen_items_and_passes_to_unlock_level_2(self) -> None:
        self.repo.ensure_user("u_pass", level=1)
        # Mark one L1 question and one scenario as already seen
        first_q = self.repo.list_questions(level=1)[0]["id"]
        first_s = self.repo.list_scenarios()[0]["id"]
        self.repo.record_attempt("u_pass", "question", first_q, "A", 70, True, AttemptContext.ONBOARDING.value)
        self.repo.record_attempt("u_pass", "scenario", first_s, "up", 70, True, AttemptContext.PRACTICE.value)

        asmt = start_assessment(self.repo, "u_pass", target_level=1)
        items = asmt["items"]
        q_items = [i for i in items if i["item_type"] == "question"]
        s_items = [i for i in items if i["item_type"] == "scenario"]
        self.assertEqual(len(q_items), 10)
        self.assertEqual(len(s_items), 2)
        self.assertNotIn(first_q, {i["item_id"] for i in q_items})
        self.assertNotIn(first_s, {i["item_id"] for i in s_items})

        # 10/12 correct (83.3%) at 85% confidence -> low Brier, passes!
        answers = self._build_answers(items, correct_count=10, confidence=85)
        res = submit_assessment(self.repo, "u_pass", asmt["assessment_id"], answers)
        self.assertTrue(res["passed"])
        self.assertGreaterEqual(res["score"], 70.0)
        self.assertLessEqual(res["brier"], 0.25)
        self.assertEqual(res["new_level"], 2)
        self.assertIn("explain_stock", res["unlocked"])
        self.assertEqual(self.repo.get_user_level("u_pass"), 2)
        self.assertIn("explain_stock", get_user_unlocks(self.repo, "u_pass", 2))

        # Double submission must be rejected
        with self.assertRaises(ValidationDomainError):
            submit_assessment(self.repo, "u_pass", asmt["assessment_id"], answers)

    def test_assessment_fail_updates_plan_and_blocks_level_up(self) -> None:
        self.repo.ensure_user("u_fail", level=1)
        asmt = start_assessment(self.repo, "u_fail", target_level=1)
        # Only 5/12 correct (41.7%) -> fail
        answers = self._build_answers(asmt["items"], correct_count=5, confidence=80)
        res = submit_assessment(self.repo, "u_fail", asmt["assessment_id"], answers)
        self.assertFalse(res["passed"])
        self.assertIsNone(res["new_level"])
        self.assertEqual(res["unlocked"], [])
        self.assertEqual(self.repo.get_user_level("u_fail"), 1)
        # Plan must exist/be updated for remediation
        plan = get_plan(self.repo, "u_fail")
        self.assertEqual(plan["level"], 1)
        self.assertGreater(len(plan["lessons"]), 0)

    def test_assessment_fails_when_brier_exceeds_configurable_threshold(self) -> None:
        self.repo.ensure_user("u_brier", level=1)
        strict_cfg = EducationConfig(assessment_pass_accuracy=0.70, assessment_max_brier=0.20)
        asmt = start_assessment(self.repo, "u_brier", target_level=1, cfg=strict_cfg)
        # 9/12 correct (75% >= 70%), but 100% confidence -> Brier = 3/12 = 0.25 > 0.20 -> FAIL!
        answers = self._build_answers(asmt["items"], correct_count=9, confidence=100)
        res = submit_assessment(self.repo, "u_brier", asmt["assessment_id"], answers, cfg=strict_cfg)
        self.assertEqual(res["score"], 75.0)
        self.assertAlmostEqual(res["brier"], 0.25, places=4)
        self.assertFalse(res["passed"])


if __name__ == "__main__":
    unittest.main()
