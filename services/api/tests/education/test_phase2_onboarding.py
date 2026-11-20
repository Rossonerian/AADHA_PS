"""Phase 2 tests: 120-question bank invariants, adaptive staircase, Brier score, simulated users."""
from __future__ import annotations

import random
import sqlite3
import unittest

from services.api.app.education.enums import SkillArea
from services.api.app.education.loader import load_seed_directory
from services.api.app.education.onboarding import answer_onboarding, start_onboarding
from services.api.app.education.repository import EducationRepository, apply_migrations
from services.api.app.education.scoring import compute_brier_score


class TestPhase2Onboarding(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_migrations(self.conn)
        self.repo = EducationRepository(self.conn)
        load_seed_directory(self.repo)

    def tearDown(self) -> None:
        self.conn.close()

    def test_question_bank_coverage_meets_prompt_contract(self) -> None:
        all_qs = self.repo.list_questions()
        self.assertGreaterEqual(len(all_qs), 80)
        for lvl in (1, 2, 3):
            for skill in SkillArea:
                subset = self.repo.list_questions(level=lvl, skill_area=skill.value)
                self.assertGreaterEqual(
                    len(subset),
                    10,
                    f"Level {lvl} skill {skill.value} has only {len(subset)} questions (need >= 10)",
                )

    def test_brier_score_exact_math(self) -> None:
        # Perfect 100% confident & correct -> 0.0
        self.assertAlmostEqual(compute_brier_score([(100, True), (100, True)]), 0.0, places=4)
        # 50% coin-flip -> always 0.25 regardless of correctness
        self.assertAlmostEqual(compute_brier_score([(50, True), (50, False)]), 0.25, places=4)
        # 90% confident, 50% accurate -> ((0.1^2) + (0.9^2))/2 = 0.41
        self.assertAlmostEqual(compute_brier_score([(90, True), (90, False)]), 0.41, places=4)
        # Out-of-bounds confidence rejected
        with self.assertRaises(ValueError):
            compute_brier_score([(49, True)])

    def _run_simulated_user(self, user_id: str, strategy: str):
        rng = random.Random(42)
        started = start_onboarding(self.repo, user_id=user_id, user_name=user_id)
        session_id = started["session_id"]
        q = started["question"]
        self.assertEqual(q["difficulty"], 3, "Onboarding must start at medium difficulty (3)")

        asked = []
        difficulties = []
        step = 0
        result = None
        while q is not None:
            asked.append(q["id"])
            difficulties.append(q["difficulty"])
            full_q = self.repo.get_question(q["id"])
            assert full_q is not None
            correct_ans = full_q["answer"]
            wrong_ans = next(opt for opt in full_q["options"] if opt != correct_ans)

            if strategy == "all_correct":
                ans, conf = correct_ans, 90
            elif strategy == "all_wrong":
                ans, conf = wrong_ans, 80
            elif strategy == "random":
                ans = rng.choice(full_q["options"])
                conf = 50
            elif strategy == "overconfident":
                ans = correct_ans if (step % 2 == 0) else wrong_ans
                conf = 98
            else:
                raise ValueError(strategy)

            resp = answer_onboarding(
                self.repo,
                user_id=user_id,
                session_id=session_id,
                question_id=q["id"],
                answer=ans,
                confidence=conf,
            )
            step += 1
            q = resp["next_question"]
            result = resp["result"]

        self.assertGreaterEqual(len(asked), 12)
        self.assertLessEqual(len(asked), 15)
        self.assertEqual(len(asked), len(set(asked)), "Duplicate questions asked in onboarding")
        assert result is not None
        return result, difficulties

    def test_simulated_users_land_at_sensible_levels_and_brier(self) -> None:
        res_good, diffs_good = self._run_simulated_user("sim_all_correct", "all_correct")
        self.assertEqual(res_good["level"], 4)
        self.assertAlmostEqual(res_good["brier"], 0.01, places=4)
        self.assertGreater(max(diffs_good), 3, "Difficulty should rise after correct answers")

        res_bad, diffs_bad = self._run_simulated_user("sim_all_wrong", "all_wrong")
        self.assertEqual(res_bad["level"], 1)
        self.assertAlmostEqual(res_bad["brier"], 0.64, places=4)
        self.assertLess(min(diffs_bad), 3, "Difficulty should drop after wrong answers")

        res_rand, _ = self._run_simulated_user("sim_random", "random")
        self.assertEqual(res_rand["level"], 1)
        self.assertAlmostEqual(res_rand["brier"], 0.25, places=4)

        res_over, _ = self._run_simulated_user("sim_overconfident", "overconfident")
        self.assertEqual(res_over["level"], 1, "Overconfident 50% user must be capped at Level 1")
        self.assertAlmostEqual(res_over["brier"], 0.4484, places=4)


if __name__ == "__main__":
    unittest.main()
