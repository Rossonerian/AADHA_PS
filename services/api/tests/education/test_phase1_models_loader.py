"""Phase 1 tests: fresh DB migration upgrade/downgrade, constraints, and YAML loader."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.api.app.education.loader import load_yaml_file
from services.api.app.education.repository import (
    EducationRepository,
    apply_migrations,
    revert_migrations,
)


class TestPhase1ModelsAndLoader(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_migrations(self.conn)
        self.repo = EducationRepository(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_migration_creates_all_sot_tables_and_reverts_cleanly(self) -> None:
        tables = {
            r["name"]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "users",
            "unlocks",
            "skill_scores",
            "questions",
            "attempts",
            "lessons",
            "plans",
            "scenarios",
            "edu_sessions",
            "edu_explain_cache",
        }
        self.assertTrue(expected.issubset(tables), f"Missing tables: {expected - tables}")

        revert_migrations(self.conn)
        remaining = {
            r["name"]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertNotIn("questions", remaining)
        self.assertNotIn("unlocks", remaining)
        self.assertIn("users", remaining)  # Hardhik's table untouched

        # Re-apply cleanly
        apply_migrations(self.conn)
        self.assertIn("questions", {
            r["name"]
            for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        })

    def test_check_constraints_enforce_sot_invariants(self) -> None:
        self.repo.ensure_user("u1")
        # Confidence out of 50-100 range must fail
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.record_attempt("u1", "question", "q1", "A", 40, True, "onboarding")
        # Invalid tool unlock must fail
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO unlocks (user_id, tool) VALUES ('u1', 'invalid_tool')")
        # Invalid data_origin must fail
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO questions (id, level, skill_area, difficulty, text, options, answer, explanation, data_origin) "
                "VALUES ('q_bad', 1, 'basics', 3, 't', '[\"a\"]', 'a', 'exp', 'unknown')"
            )

    def test_yaml_loader_imports_sample_and_blocks_bad_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sample = Path(td) / "sample.yaml"
            sample.write_text(
                """
questions:
  - id: q_sample_1
    level: 1
    skill_area: basics
    difficulty: 3
    text: "What does NSE stand for?"
    options: ["National Stock Exchange", "New Securities Entity", "National Savings Exchange", "None"]
    answer: "National Stock Exchange"
    explanation: "NSE stands for National Stock Exchange of India."
    tags: ["basics"]
    data_origin: synthetic
""",
                encoding="utf-8",
            )
            summary = load_yaml_file(self.repo, sample)
            self.assertEqual(summary.questions, 1)
            q = self.repo.get_question("q_sample_1")
            self.assertIsNotNone(q)
            self.assertEqual(q["data_origin"], "synthetic")

            # Idempotent reload should not duplicate or fail
            summary2 = load_yaml_file(self.repo, sample)
            self.assertEqual(summary2.questions, 1)

            # Advisory content in YAML must be rejected by guardrails
            bad = Path(td) / "bad.yaml"
            bad.write_text(
                """
questions:
  - id: q_bad_advice
    level: 1
    skill_area: basics
    difficulty: 3
    text: "Test?"
    options: ["A", "B"]
    answer: "A"
    explanation: "You should buy this stock now, price target is 500!"
    data_origin: synthetic
""",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_yaml_file(self.repo, bad)


if __name__ == "__main__":
    unittest.main()
