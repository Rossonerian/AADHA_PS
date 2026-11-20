"""End-to-End FastAPI HTTP integration, security isolation, and guardrail verification tests."""

from __future__ import annotations

import unittest
import uuid
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import guardrails
from app.education.loader import load_seed_directory
from app.education.repository import EducationRepository
from app.education.scenarios import recompute_scenario_outcome
from tests.education._market_seed import use_education_price_seed


class TestE2ESecurityAndGuardrails(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def _app_db_and_seeds(
        self,
        client: TestClient,
        db_session: Session,
        make_jwt: Callable[..., str],
    ) -> Generator[None, None, None]:
        """Real app + Alembic-migrated test DB (conftest), education seeds, seeded prices."""
        restore_market = use_education_price_seed()
        try:
            self.client = client
            self.make_jwt = make_jwt
            self.repo = EducationRepository(db_session)
            load_seed_directory(self.repo)
            yield
        finally:
            restore_market()

    def _auth_headers(self, level: int = 1, name: str = "Learner") -> dict[str, str]:
        """Bearer headers for a fresh UUID user persisted at `level`."""
        user_id = str(uuid.uuid4())
        self.repo.ensure_user(user_id, name=name, level=level)
        self.repo.set_user_level(user_id, level)
        token = self.make_jwt(user_id, user_metadata={"name": name})
        return {"Authorization": f"Bearer {token}"}

    def test_full_learner_lifecycle_via_http_api(self) -> None:
        # 1. Health & /me
        h = self.client.get("/api/v1/health")
        self.assertEqual(h.status_code, 200)
        self.assertEqual(h.json()["status"], "ok")

        headers = self._auth_headers(level=1, name="Riya")
        me = self.client.get("/api/v1/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["unlocks"], ["scenarios", "red_flag_check"])

        # 2. Onboarding end-to-end (answer all wrong so user lands cleanly at Level 1)
        s = self.client.post("/api/v1/onboarding/start", headers=headers)
        self.assertEqual(s.status_code, 200)
        sid = s.json()["session_id"]
        q = s.json()["question"]
        result = None
        while q is not None:
            full_q = self.repo.get_question(q["id"])
            assert full_q is not None
            wrong = next(o for o in full_q["options"] if o != full_q["answer"])
            r = self.client.post(
                "/api/v1/onboarding/answer",
                headers=headers,
                json={
                    "session_id": sid,
                    "question_id": q["id"],
                    "answer": wrong,
                    "confidence": 60,
                },
            )
            self.assertEqual(r.status_code, 200)
            payload = r.json()
            q = payload["next_question"]
            result = payload["result"]
        assert result is not None
        self.assertEqual(result["level"], 1)

        # 3. Plan & Lesson check
        plan = self.client.get("/api/v1/plan", headers=headers)
        self.assertEqual(plan.status_code, 200)
        first_lid = plan.json()["lessons"][0]["id"]
        lesson = self.client.get(f"/api/v1/lessons/{first_lid}", headers=headers)
        self.assertEqual(lesson.status_code, 200)
        full_lesson = self.repo.get_lesson(first_lid)
        assert full_lesson is not None
        chk = self.client.post(
            f"/api/v1/lessons/{first_lid}/check",
            headers=headers,
            json={
                "answers": [
                    {"question_id": cq["id"], "answer": cq["answer"], "confidence": 85}
                    for cq in full_lesson["check_questions"]
                ]
            },
        )
        self.assertEqual(chk.status_code, 200)
        self.assertTrue(chk.json()["passed"])

        # 4. Explain a Stock locked at Level 1 -> 403 TOOL_LOCKED
        locked = self.client.get(
            "/api/v1/explain?symbol=PAYTM&year=2021", headers=headers
        )
        self.assertEqual(locked.status_code, 403)
        self.assertEqual(locked.json()["code"], "TOOL_LOCKED")
        self.assertEqual(locked.json()["required_level"], 2)

        # 5. Scenario practice
        sc_next = self.client.get(
            "/api/v1/scenarios/next?difficulty=2", headers=headers
        )
        self.assertEqual(sc_next.status_code, 200)
        sc_id = sc_next.json()["id"]
        sc_ans = self.client.post(
            f"/api/v1/scenarios/{sc_id}/answer",
            headers=headers,
            json={"direction": "down", "confidence": 80, "clues": ["auditor"]},
        )
        self.assertEqual(sc_ans.status_code, 200)
        self.assertIn("index_pct", sc_ans.json()["outcome"])

        # 6. Level 1 Assessment -> Pass -> Level 2 -> Explain a Stock UNLOCKED!
        asmt = self.client.post("/api/v1/assessments/1/start", headers=headers)
        self.assertEqual(asmt.status_code, 200)
        aid = asmt.json()["assessment_id"]
        answers = []
        for item in asmt.json()["items"]:
            if item["item_type"] == "question":
                q_rec = self.repo.get_question(item["item_id"])
                assert q_rec is not None
                ans = q_rec["answer"]
            else:
                sc = self.repo.get_scenario(item["item_id"])
                assert sc is not None
                ans = recompute_scenario_outcome(
                    sc["symbol"], sc["as_of_date"], sc["window_days"]
                )["actual_direction"]
            answers.append(
                {"item_id": item["item_id"], "answer": ans, "confidence": 90}
            )

        sub = self.client.post(
            f"/api/v1/assessments/{aid}/submit",
            headers=headers,
            json={"answers": answers},
        )
        self.assertEqual(sub.status_code, 200)
        self.assertTrue(sub.json()["passed"])
        self.assertEqual(sub.json()["new_level"], 2)
        self.assertIn("explain_stock", sub.json()["unlocked"])

        # Now Explain a Stock returns 200!
        exp = self.client.get("/api/v1/explain?symbol=PAYTM&year=2021", headers=headers)
        self.assertEqual(exp.status_code, 200)
        self.assertEqual(exp.json()["symbol"], "PAYTM")

        # Dashboard still locked at Level 2 -> 403 TOOL_LOCKED (required_level 4)
        dash_locked = self.client.get("/api/v1/me/dashboard", headers=headers)
        self.assertEqual(dash_locked.status_code, 403)
        self.assertEqual(dash_locked.json()["required_level"], 4)

    def test_security_auth_idor_sqli_and_guardrails(self) -> None:
        # Invalid bearer token -> 401
        unauth = self.client.get(
            "/api/v1/plan", headers={"Authorization": "Bearer invalid_xyz"}
        )
        self.assertEqual(unauth.status_code, 401)

        # Cross-user IDOR protection on onboarding session
        u1 = self._auth_headers(level=1)
        u2 = self._auth_headers(level=1)
        s = self.client.post("/api/v1/onboarding/start", headers=u1).json()
        hijack = self.client.post(
            "/api/v1/onboarding/answer",
            headers=u2,
            json={
                "session_id": s["session_id"],
                "question_id": s["question"]["id"],
                "answer": "x",
                "confidence": 70,
            },
        )
        self.assertEqual(hijack.status_code, 404)

        # Out-of-range confidence -> 422
        bad_conf = self.client.post(
            "/api/v1/onboarding/answer",
            headers=u1,
            json={
                "session_id": s["session_id"],
                "question_id": s["question"]["id"],
                "answer": "x",
                "confidence": 10,
            },
        )
        self.assertEqual(bad_conf.status_code, 422)

        # SQL injection attempt in query/path -> clean 404, never 500
        l2 = self._auth_headers(level=2)
        sqli = self.client.get(
            "/api/v1/explain?symbol=PAYTM';DROP TABLE questions;--&year=2021",
            headers=l2,
        )
        self.assertEqual(sqli.status_code, 422)
        unknown = self.client.get(
            "/api/v1/explain?symbol=NONEXISTENT99&year=2021", headers=l2
        )
        self.assertEqual(unknown.status_code, 404)
        self.assertGreaterEqual(len(self.repo.list_questions()), 120)

        # Guardrails EN + Hinglish enforcement
        for banned in [
            "You should buy TCS immediately!",
            "Yeh stock abhi kharid lo, pakka badhega!",
            "Price target is Rs 2500 next month.",
            "Bech do isko aaj hi!",
        ]:
            res = guardrails.check_output(banned)
            self.assertFalse(res.ok, f"Guardrail failed to block: {banned}")
            self.assertIn("educational platform", res.text)


if __name__ == "__main__":
    unittest.main()
