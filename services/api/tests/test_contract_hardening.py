"""Contract-hardening tests for Tasks 1-5: provenance, scenario validation, option shuffling."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.models import UserRecord
from app.core.provenance import aggregate_data_origin
from app.education.exceptions import ValidationDomainError
from app.education.loader import load_seed_directory
from app.education.repository import EducationRepository
from app.education.scenarios import answer_scenario, scenario_outcome
from app.education.scoring import shuffle_options_for_question
from app.verifier.models import Claim, Source, Submission
from tests.education._market_seed import use_education_price_seed


def test_aggregate_data_origin_conservative_rules() -> None:
    """`aggregate_data_origin` returns 'real' only when all inputs are 'real'."""
    assert aggregate_data_origin([], empty_default="synthetic") == "synthetic"
    assert aggregate_data_origin([], empty_default="real") == "real"
    assert aggregate_data_origin(["real", "real"]) == "real"
    assert aggregate_data_origin(["synthetic", "synthetic"]) == "synthetic"
    assert aggregate_data_origin(["real", "synthetic"]) == "mixed"
    assert aggregate_data_origin(["real", None]) == "mixed"
    assert aggregate_data_origin(["mixed", "real"]) == "mixed"
    assert aggregate_data_origin(["mixed", "synthetic"]) == "mixed"


def test_education_and_platform_endpoints_include_top_level_data_origin_and_mixed(
    client: TestClient,
    db_session: Session,
    make_jwt: Callable[..., str],
) -> None:
    """All 8 endpoints expose top-level `data_origin` across synthetic, mixed, and real cases."""
    restore_market = use_education_price_seed()
    try:
        repo = EducationRepository(db_session)
        load_seed_directory(repo)

        user_id = str(uuid.uuid4())
        headers = {
            "Authorization": f"Bearer {make_jwt(user_id, email='origin@test.in')}"
        }

        # 1. GET /me -> 'real'
        me_resp = client.get("/api/v1/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["data_origin"] == "real"

        # 2. POST /onboarding/start & POST /onboarding/answer -> 'synthetic' for seed questions
        start_resp = client.post("/api/v1/onboarding/start", headers=headers)
        assert start_resp.status_code == 200
        start_data = start_resp.json()
        assert start_data["data_origin"] == "synthetic"

        session_id = start_data["session_id"]
        q = start_data["question"]
        ans_data: dict[str, object] = {}
        while q is not None:
            full_q = repo.get_question(q["id"])
            assert full_q is not None
            ans_resp = client.post(
                "/api/v1/onboarding/answer",
                headers=headers,
                json={
                    "session_id": session_id,
                    "question_id": q["id"],
                    "answer": full_q["answer"],
                    "confidence": 90,
                },
            )
            assert ans_resp.status_code == 200
            ans_data = ans_resp.json()
            assert ans_data["data_origin"] == "synthetic"
            q = ans_data["next_question"]
        assert ans_data["result"] is not None

        # 3. GET /plan -> 'synthetic' when plan lessons are synthetic
        plan_resp = client.get("/api/v1/plan", headers=headers)
        assert plan_resp.status_code == 200
        assert plan_resp.json()["data_origin"] == "synthetic"

        # 4. POST /assessments/{level}/start & /submit -> matches item origins conservatively
        asmt_start_resp = client.post("/api/v1/assessments/3/start", headers=headers)
        assert asmt_start_resp.status_code == 200
        asmt_start = asmt_start_resp.json()
        expected_asmt_origin = aggregate_data_origin(
            [item["prompt"]["data_origin"] for item in asmt_start["items"]]
        )
        assert asmt_start["data_origin"] == expected_asmt_origin
        assert asmt_start["data_origin"] in ("real", "synthetic", "mixed")

        asmt_answers = []
        for item in asmt_start["items"]:
            if item["item_type"] == "question":
                rec = repo.get_question(item["item_id"])
                assert rec is not None
                chosen = rec["answer"]
            else:
                sc = repo.get_scenario(item["item_id"])
                assert sc is not None
                chosen = scenario_outcome(sc)[0]["actual_direction"]
            asmt_answers.append(
                {"item_id": item["item_id"], "answer": chosen, "confidence": 85}
            )
        asmt_submit_resp = client.post(
            f"/api/v1/assessments/{asmt_start['assessment_id']}/submit",
            headers=headers,
            json={"answers": asmt_answers},
        )
        assert asmt_submit_resp.status_code == 200
        assert asmt_submit_resp.json()["data_origin"] == expected_asmt_origin

        # 5. GET /me/dashboard -> conservative aggregation across user's attempts
        dash_resp = client.get("/api/v1/me/dashboard", headers=headers)
        assert dash_resp.status_code == 200
        assert dash_resp.json()["data_origin"] in ("synthetic", "mixed")

        # Pure synthetic user (all synthetic questions + forced synthetic scenario) -> 'synthetic'
        syn_user = str(uuid.uuid4())
        repo.ensure_user(syn_user, level=4)
        h_syn = {"Authorization": f"Bearer {make_jwt(syn_user)}"}
        syn_q = repo.list_questions(level=1)[0]
        repo.record_attempt(
            syn_user,
            "question",
            syn_q["id"],
            syn_q["answer"],
            80,
            True,
            "onboarding",
        )
        assert (
            client.get("/api/v1/me/dashboard", headers=h_syn).json()["data_origin"]
            == "synthetic"
        )

        # Adding one real question attempt turns /me/dashboard from 'synthetic' to 'mixed'
        real_q = dict(syn_q)
        real_q["data_origin"] = "real"
        repo.upsert_question(real_q)
        assert (
            client.get("/api/v1/me/dashboard", headers=h_syn).json()["data_origin"]
            == "real"
        )
        other_syn_q = repo.list_questions(level=1)[1]
        repo.record_attempt(
            syn_user,
            "question",
            other_syn_q["id"],
            other_syn_q["answer"],
            80,
            True,
            "onboarding",
        )
        assert (
            client.get("/api/v1/me/dashboard", headers=h_syn).json()["data_origin"]
            == "mixed"
        )

        # Assessment with 1 real question + 9 synthetic questions -> 'mixed'
        mix_user = str(uuid.uuid4())
        repo.ensure_user(mix_user, level=1)
        h_mix = {"Authorization": f"Bearer {make_jwt(mix_user)}"}
        asmt_mix = client.post("/api/v1/assessments/1/start", headers=h_mix).json()
        q_origins = [
            i["prompt"]["data_origin"]
            for i in asmt_mix["items"]
            if i["item_type"] == "question"
        ]
        assert "real" in q_origins and "synthetic" in q_origins
        assert asmt_mix["data_origin"] == "mixed"

        # GET /plan with 1 real lesson + remaining synthetic lessons -> 'mixed'
        mix_plan_before = client.get("/api/v1/plan", headers=h_mix).json()
        first_lid = mix_plan_before["lessons"][0]["id"]
        real_lesson = repo.get_lesson(first_lid)
        assert real_lesson is not None
        real_lesson["data_origin"] = "real"
        repo.upsert_lesson(real_lesson)
        assert (
            client.get("/api/v1/plan", headers=h_mix).json()["data_origin"] == "mixed"
        )
    finally:
        restore_market()


def test_submissions_mine_derives_mixed_when_real_and_synthetic_exist(
    client: TestClient,
    db_session: Session,
    make_jwt: Callable[..., str],
) -> None:
    """`GET /submissions/mine` returns 'mixed' when both real and synthetic rows exist."""
    user_id = str(uuid.uuid4())
    uid = uuid.UUID(user_id)
    db_session.add(UserRecord(id=user_id, name="Mixed Submissions", current_level=3))
    src_real = Source(platform="paste", handle="real-src", data_origin="real")
    src_syn = Source(platform="paste", handle="syn-src", data_origin="synthetic")
    db_session.add_all([src_real, src_syn])
    db_session.flush()

    now = datetime.now(UTC)
    sub_real = Submission(
        user_id=uid,
        source_id=src_real.id,
        raw_content="TCS up",
        content_hash="1" * 64,
        captured_at=now,
        data_origin="real",
    )
    sub_syn = Submission(
        user_id=uid,
        source_id=src_syn.id,
        raw_content="INFY up",
        content_hash="2" * 64,
        captured_at=now,
        data_origin="synthetic",
    )
    db_session.add_all([sub_real, sub_syn])
    db_session.flush()
    db_session.add_all(
        [
            Claim(
                submission_id=sub_real.id,
                symbol="TCS",
                direction="up",
                window_days=20,
                scorable=False,
                status="needs_review",
                data_origin="real",
            ),
            Claim(
                submission_id=sub_syn.id,
                symbol="INFY",
                direction="up",
                window_days=20,
                scorable=False,
                status="needs_review",
                data_origin="synthetic",
            ),
        ]
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {make_jwt(user_id)}"}
    resp = client.get("/api/v1/submissions/mine", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["data_origin"] == "mixed"


def test_scenarios_answer_rejects_flat_with_422_validation_error(
    client: TestClient,
    db_session: Session,
    make_jwt: Callable[..., str],
) -> None:
    """`POST /scenarios/{id}/answer` accepts only `up|down` and rejects `flat` with 422."""
    restore_market = use_education_price_seed()
    try:
        repo = EducationRepository(db_session)
        load_seed_directory(repo)

        user_id = str(uuid.uuid4())
        repo.ensure_user(user_id, name="Scenario User", level=1)
        headers = {"Authorization": f"Bearer {make_jwt(user_id)}"}

        next_sc = client.get("/api/v1/scenarios/next", headers=headers)
        assert next_sc.status_code == 200
        sc_id = next_sc.json()["id"]

        flat_resp = client.post(
            f"/api/v1/scenarios/{sc_id}/answer",
            headers=headers,
            json={"direction": "flat", "confidence": 70, "clues": []},
        )
        assert flat_resp.status_code == 422
        assert flat_resp.json()["error"]["code"] == "VALIDATION_ERROR"

        with pytest.raises(ValidationDomainError) as exc_info:
            answer_scenario(
                repo,
                user_id=user_id,
                user_level=1,
                scenario_id=sc_id,
                direction="flat",
                confidence=70,
                clues=[],
            )
        assert exc_info.value.code == "VALIDATION_ERROR"

        up_resp = client.post(
            f"/api/v1/scenarios/{sc_id}/answer",
            headers=headers,
            json={"direction": "up", "confidence": 70, "clues": []},
        )
        assert up_resp.status_code == 200
    finally:
        restore_market()


def test_question_options_stable_shuffle_and_grading_across_flows(
    client: TestClient,
    db_session: Session,
    make_jwt: Callable[..., str],
) -> None:
    """Stable per-question shuffle removes index-0 bias while preserving option grading."""
    repo_root = Path(__file__).resolve().parents[3]
    qs = yaml.safe_load(
        (repo_root / "data/seed/education/questions.yaml").read_text(encoding="utf-8")
    )["questions"]
    lessons = yaml.safe_load(
        (repo_root / "data/seed/education/lessons.yaml").read_text(encoding="utf-8")
    )["lessons"]

    # Deterministic stability & index-0 anti-bias check across full question & lesson banks
    q_first = 0
    for q in qs:
        s1 = shuffle_options_for_question(q["id"], q["options"])
        s2 = shuffle_options_for_question(q["id"], q["options"])
        assert s1 == s2
        assert sorted(s1) == sorted(q["options"])
        if s1[0] == q["answer"]:
            q_first += 1
    assert q_first < len(qs) * 0.6

    cq_first = 0
    total_cqs = 0
    for lesson in lessons:
        for cq in lesson["check_questions"]:
            total_cqs += 1
            s1 = shuffle_options_for_question(cq["id"], cq["options"])
            s2 = shuffle_options_for_question(cq["id"], cq["options"])
            assert s1 == s2
            assert sorted(s1) == sorted(cq["options"])
            if s1[0] == cq["answer"]:
                cq_first += 1
    assert cq_first < total_cqs * 0.6

    # HTTP integration: shuffled options grade cleanly across onboarding, lessons, and assessments
    restore_market = use_education_price_seed()
    try:
        repo = EducationRepository(db_session)
        load_seed_directory(repo)

        user_id = str(uuid.uuid4())
        headers = {"Authorization": f"Bearer {make_jwt(user_id)}"}

        plan = client.get("/api/v1/plan", headers=headers).json()
        lid = plan["lessons"][0]["id"]
        lesson_detail_1 = client.get(f"/api/v1/lessons/{lid}", headers=headers).json()
        lesson_detail_2 = client.get(f"/api/v1/lessons/{lid}", headers=headers).json()
        assert lesson_detail_1["check_questions"] == lesson_detail_2["check_questions"]

        full_lesson = repo.get_lesson(lid)
        assert full_lesson is not None
        cq_by_id = {cq["id"]: cq for cq in full_lesson["check_questions"]}
        for pub_cq in lesson_detail_1["check_questions"]:
            assert sorted(pub_cq["options"]) == sorted(
                cq_by_id[pub_cq["id"]]["options"]
            )
            assert cq_by_id[pub_cq["id"]]["answer"] in pub_cq["options"]

        chk = client.post(
            f"/api/v1/lessons/{lid}/check",
            headers=headers,
            json={
                "answers": [
                    {
                        "question_id": pub_cq["id"],
                        "answer": cq_by_id[pub_cq["id"]]["answer"],
                        "confidence": 85,
                    }
                    for pub_cq in lesson_detail_1["check_questions"]
                ]
            },
        )
        assert chk.status_code == 200
        assert chk.json()["passed"] is True
        assert chk.json()["score_pct"] == 100.0
    finally:
        restore_market()
