"""Phase 4 tests: unseen items, pass/fail/calibration thresholds, level-up unlocks.

Also covers the fail -> plan update path.
"""

from __future__ import annotations

import sqlite3
import unittest

from app.education.assessments import start_assessment, submit_assessment
from app.education.config import EducationConfig
from app.education.enums import AttemptContext, AttemptItemType
from app.education.exceptions import ValidationDomainError
from app.education.learning import get_plan, get_user_unlocks
from app.education.loader import load_seed_directory
from app.education.repository import EducationRepository, apply_migrations
from app.education.scenarios import recompute_scenario_outcome
from tests.education._market_seed import use_education_price_seed


class TestPhase4Assessments(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(use_education_price_seed())
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
                ans = (
                    q["answer"]
                    if should_be_right
                    else next(o for o in q["options"] if o != q["answer"])
                )
            else:
                sc = self.repo.get_scenario(item["item_id"])
                assert sc is not None
                out = recompute_scenario_outcome(
                    sc["symbol"], sc["as_of_date"], sc["window_days"]
                )
                actual = out["actual_direction"]
                ans = (
                    actual if should_be_right else ("down" if actual == "up" else "up")
                )
            answers.append(
                {"item_id": item["item_id"], "answer": ans, "confidence": confidence}
            )
        return answers

    def test_assessment_uses_unseen_items_and_passes_to_unlock_level_2(self) -> None:
        self.repo.ensure_user("u_pass", level=1)
        # Mark one L1 question and one scenario as already seen
        first_q = self.repo.list_questions(level=1)[0]["id"]
        first_s = self.repo.list_scenarios()[0]["id"]
        self.repo.record_attempt(
            "u_pass",
            "question",
            first_q,
            "A",
            70,
            True,
            AttemptContext.ONBOARDING.value,
        )
        self.repo.record_attempt(
            "u_pass", "scenario", first_s, "up", 70, True, AttemptContext.PRACTICE.value
        )

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
        strict_cfg = EducationConfig(
            assessment_pass_accuracy=0.70, assessment_max_brier=0.20
        )
        asmt = start_assessment(self.repo, "u_brier", target_level=1, cfg=strict_cfg)
        # 9/12 correct (75% >= 70%), but 100% confidence -> Brier = 3/12 = 0.25 > 0.20 -> FAIL!
        answers = self._build_answers(asmt["items"], correct_count=9, confidence=100)
        res = submit_assessment(
            self.repo, "u_brier", asmt["assessment_id"], answers, cfg=strict_cfg
        )
        self.assertEqual(res["score"], 75.0)
        self.assertAlmostEqual(res["brier"], 0.25, places=4)
        self.assertFalse(res["passed"])

    def test_assessment_rejects_duplicate_item_substitution_before_scoring(
        self,
    ) -> None:
        self.repo.ensure_user("u_duplicate_assessment", level=1)
        assessment = start_assessment(self.repo, "u_duplicate_assessment", 1)
        answers = self._build_answers(assessment["items"], 12, 50)
        answers[-1] = dict(answers[0])
        with self.assertRaises(ValidationDomainError) as duplicate:
            submit_assessment(
                self.repo,
                "u_duplicate_assessment",
                assessment["assessment_id"],
                answers,
            )
        self.assertEqual(duplicate.exception.code, "DUPLICATE_ITEM")
        self.assertEqual(
            self.repo.list_attempts(
                user_id="u_duplicate_assessment", context="assessment"
            ),
            [],
        )

    def test_level_one_user_cannot_start_higher_level_assessment(self) -> None:
        self.repo.ensure_user("u_gate", level=1)
        for target in (2, 3):
            with self.assertRaises(ValidationDomainError) as ctx:
                start_assessment(self.repo, "u_gate", target_level=target)
            self.assertEqual(ctx.exception.code, "ASSESSMENT_LEVEL_MISMATCH")

    def test_pass_promotes_by_exactly_one_level_and_never_skips(self) -> None:
        self.repo.ensure_user("u_noskip", level=1)
        asmt = start_assessment(self.repo, "u_noskip", target_level=1)
        # Simulate a tampered/stale session that stores a higher target than the level.
        self.conn.execute(
            "UPDATE edu_sessions SET target_level = 3 WHERE id = ?",
            (asmt["assessment_id"],),
        )
        self.conn.commit()
        answers = self._build_answers(asmt["items"], correct_count=12, confidence=85)
        with self.assertRaises(ValidationDomainError) as ctx:
            submit_assessment(self.repo, "u_noskip", asmt["assessment_id"], answers)
        self.assertEqual(ctx.exception.code, "ASSESSMENT_LEVEL_CHANGED")
        self.assertEqual(self.repo.get_user_level("u_noskip"), 1)

        fresh = start_assessment(self.repo, "u_noskip", target_level=1)
        answers = self._build_answers(fresh["items"], correct_count=12, confidence=85)
        result = submit_assessment(
            self.repo, "u_noskip", fresh["assessment_id"], answers
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["new_level"], 2)
        self.assertEqual(self.repo.get_user_level("u_noskip"), 2)

    def test_double_submit_is_idempotent_and_promotes_once(self) -> None:
        from app.education.assessments import _claim_session

        self.repo.ensure_user("u_double", level=1)
        asmt = start_assessment(self.repo, "u_double", target_level=1)
        answers = self._build_answers(asmt["items"], correct_count=12, confidence=85)
        # A racing submit that already claimed the session wins; the loser grades nothing.
        self.assertTrue(_claim_session(self.repo, asmt["assessment_id"]))
        self.assertFalse(_claim_session(self.repo, asmt["assessment_id"]))
        with self.assertRaises(ValidationDomainError) as ctx:
            submit_assessment(self.repo, "u_double", asmt["assessment_id"], answers)
        self.assertEqual(ctx.exception.code, "ASSESSMENT_ALREADY_SUBMITTED")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.repo.get_user_level("u_double"), 1)

    def test_failed_grading_releases_the_claim(self) -> None:
        self.repo.ensure_user("u_release", level=1)
        asmt = start_assessment(self.repo, "u_release", target_level=1)
        answers = self._build_answers(asmt["items"], correct_count=12, confidence=85)
        answers[0]["confidence"] = "not-a-number"
        with self.assertRaises(ValueError):
            submit_assessment(self.repo, "u_release", asmt["assessment_id"], answers)
        answers[0]["confidence"] = 85
        result = submit_assessment(
            self.repo, "u_release", asmt["assessment_id"], answers
        )
        self.assertTrue(result["passed"])
        self.assertEqual(self.repo.get_user_level("u_release"), 2)

    def test_retaking_a_lower_level_never_changes_level(self) -> None:
        self.repo.ensure_user("u_retake", level=3)
        asmt = start_assessment(self.repo, "u_retake", target_level=2)
        answers = self._build_answers(asmt["items"], correct_count=12, confidence=85)
        result = submit_assessment(
            self.repo, "u_retake", asmt["assessment_id"], answers
        )
        self.assertTrue(result["passed"])
        self.assertEqual(self.repo.get_user_level("u_retake"), 3)


if __name__ == "__main__":
    unittest.main()
