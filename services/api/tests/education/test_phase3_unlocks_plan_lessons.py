"""Phase 3 tests: SoT Section 8 unlocks, weakest-skill learning plan, and 12 micro-lessons."""

from __future__ import annotations

import sqlite3
import unittest

from app.education.enums import LessonStatus, ToolName
from app.education.exceptions import ToolLockedError
from app.education.learning import (
    build_or_update_plan,
    get_lesson_detail,
    get_plan,
    get_user_unlocks,
    require_tool_unlocked,
    submit_lesson_check,
)
from app.education.loader import load_seed_directory
from app.education.repository import EducationRepository, apply_migrations


class TestPhase3UnlocksPlanLessons(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_migrations(self.conn)
        self.repo = EducationRepository(self.conn)
        load_seed_directory(self.repo)

    def tearDown(self) -> None:
        self.conn.close()

    def test_level_unlock_progression_matches_sot_section_8(self) -> None:
        self.repo.ensure_user("u_l1", level=1)
        self.assertEqual(
            get_user_unlocks(self.repo, "u_l1", 1), ["scenarios", "red_flag_check"]
        )
        with self.assertRaises(ToolLockedError) as ctx:
            require_tool_unlocked(
                self.repo, "u_l1", ToolName.EXPLAIN_STOCK, user_level=1
            )
        self.assertEqual(ctx.exception.required_level, 2)
        self.assertEqual(ctx.exception.status_code, 403)

        self.repo.ensure_user("u_l2", level=2)
        self.assertEqual(
            get_user_unlocks(self.repo, "u_l2", 2),
            ["scenarios", "red_flag_check", "explain_stock"],
        )
        require_tool_unlocked(self.repo, "u_l2", ToolName.EXPLAIN_STOCK, user_level=2)
        with self.assertRaises(ToolLockedError) as ctx3:
            require_tool_unlocked(self.repo, "u_l2", ToolName.VERIFIER, user_level=2)
        self.assertEqual(ctx3.exception.required_level, 3)

        self.repo.ensure_user("u_l4", level=4)
        self.assertEqual(
            get_user_unlocks(self.repo, "u_l4", 4),
            ["scenarios", "red_flag_check", "explain_stock", "verifier", "dashboard"],
        )

    def test_plan_targets_weakest_skill_first_and_tracks_lesson_completion(
        self,
    ) -> None:
        self.repo.ensure_user("u_plan", level=1)
        self.repo.record_skill_scores(
            "u_plan",
            {"basics": 85.0, "reading_stock": 70.0, "judging_info": 20.0, "risk": 55.0},
            brier=0.22,
        )
        plan = build_or_update_plan(self.repo, "u_plan", level=1)
        self.assertEqual(plan["level"], 1)
        self.assertEqual(plan["progress_pct"], 0.0)
        # First lesson in plan MUST target the weakest skill ('judging_info')
        self.assertEqual(plan["lessons"][0]["skill_area"], "judging_info")
        self.assertEqual(plan["lessons"][1]["skill_area"], "risk")

        # Complete first lesson's 3 check questions
        first_id = plan["lessons"][0]["id"]
        full_lesson = self.repo.get_lesson(first_id)
        assert full_lesson is not None
        detail = get_lesson_detail(self.repo, first_id)
        self.assertEqual(len(detail["check_questions"]), 3)
        answers = [
            {"question_id": cq["id"], "answer": cq["answer"], "confidence": 85}
            for cq in full_lesson["check_questions"]
        ]
        chk = submit_lesson_check(self.repo, "u_plan", first_id, answers)
        self.assertTrue(chk["passed"])
        self.assertEqual(chk["score_pct"], 100.0)
        self.assertGreater(chk["plan_progress_pct"], 0.0)

        refreshed = get_plan(self.repo, "u_plan")
        self.assertEqual(
            refreshed["lessons"][0]["status"], LessonStatus.COMPLETED.value
        )

    def test_lesson_bank_has_at_least_8_lessons_for_l1_to_l3_with_3_checks_each(
        self,
    ) -> None:
        lessons = self.repo.list_lessons()
        self.assertGreaterEqual(len(lessons), 8)
        for lsn in lessons:
            self.assertIn(lsn["level"], (1, 2, 3))
            self.assertGreaterEqual(lsn["minutes"], 5)
            self.assertLessEqual(lsn["minutes"], 10)
            self.assertEqual(len(lsn["check_questions"]), 3)


if __name__ == "__main__":
    unittest.main()
