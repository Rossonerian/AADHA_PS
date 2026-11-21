"""Phase 4: Level-up assessments (10 unseen Qs + 2 unseen scenarios, >=70% & Brier <= 0.25)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import update

from ..core.provenance import aggregate_data_origin
from .config import DEFAULT_CONFIG, EducationConfig
from .enums import AttemptContext, AttemptItemType, SkillArea
from .exceptions import NotFoundError, ValidationDomainError
from .learning import build_or_update_plan, ensure_level_unlocks
from .models import EduSession
from .repository import EducationRepository
from .scenarios import build_public_scenario, scenario_outcome
from .scoring import (
    compute_brier_score,
    compute_skill_scores,
    shuffle_options_for_question,
)


def _claim_session(repo: EducationRepository, session_id: str) -> bool:
    """Atomically flip ``completed`` false -> true; only one concurrent caller wins."""
    if repo.is_orm:
        result = repo.conn.execute(
            update(EduSession)
            .where(EduSession.id == session_id, EduSession.completed.is_(False))
            .values(completed=True)
        )
        repo.conn.commit()
        return bool(result.rowcount)
    cur = repo.conn.execute(
        "UPDATE edu_sessions SET completed = 1 WHERE id = ? AND completed = 0",
        (session_id,),
    )
    repo.conn.commit()
    return bool(cur.rowcount == 1)


def _release_session(repo: EducationRepository, session_id: str) -> None:
    if repo.is_orm:
        repo.conn.rollback()
        repo.conn.execute(
            update(EduSession)
            .where(EduSession.id == session_id)
            .values(completed=False)
        )
        repo.conn.commit()
        return
    repo.conn.execute(
        "UPDATE edu_sessions SET completed = 0 WHERE id = ?", (session_id,)
    )
    repo.conn.commit()


def start_assessment(
    repo: EducationRepository,
    user_id: str,
    target_level: int,
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Starts a level-up assessment with 10 unseen questions + 2 unseen scenarios."""
    if not (1 <= int(target_level) <= 3):
        raise ValidationDomainError(
            "INVALID_ASSESSMENT_LEVEL",
            "Assessments are available for levels 1, 2, and 3 (advancing to levels 2, 3, and 4).",
        )

    repo.ensure_user(user_id)
    # Level gating: the assessment for level N is the gate out of level N. A learner may
    # start their current level's assessment (or re-take an already-passed lower one),
    # never a higher one.
    current_level = repo.get_user_level(user_id, default_level=1)
    if int(target_level) > current_level:
        raise ValidationDomainError(
            "ASSESSMENT_LEVEL_MISMATCH",
            f"You can only start assessments up to level {current_level} right now.",
        )
    seen_q_ids = repo.list_seen_item_ids(user_id, AttemptItemType.QUESTION.value)
    seen_s_ids = repo.list_seen_item_ids(user_id, AttemptItemType.SCENARIO.value)

    # Pick 10 unseen questions balanced across the 4 skill areas for target_level
    selected_qs: list[dict[str, Any]] = []
    per_skill_pools = {
        s.value: repo.list_questions(
            level=target_level, skill_area=s.value, exclude_ids=seen_q_ids
        )
        for s in SkillArea
    }
    # Round-robin pick up to cfg.assessment_question_count (10)
    idx = 0
    skill_order = [s.value for s in SkillArea]
    picked_q_ids = set()
    while len(selected_qs) < cfg.assessment_question_count:
        progressed = False
        for area in skill_order:
            pool = per_skill_pools[area]
            if pool and len(selected_qs) < cfg.assessment_question_count:
                q = pool.pop(0)
                selected_qs.append(q)
                picked_q_ids.add(q["id"])
                progressed = True
        if not progressed:
            break
        idx += 1

    # Fallback to unseen questions from adjacent levels if user exhausted exact level
    if len(selected_qs) < cfg.assessment_question_count:
        fallback_qs = repo.list_questions(exclude_ids=seen_q_ids | picked_q_ids)
        for q in fallback_qs:
            if len(selected_qs) >= cfg.assessment_question_count:
                break
            selected_qs.append(q)
            picked_q_ids.add(q["id"])

    # Pick 2 unseen scenarios calibrated to level difficulty
    unseen_scenarios = repo.list_scenarios(exclude_ids=seen_s_ids)
    # Prefer scenarios near target_level + 1 difficulty
    unseen_scenarios.sort(
        key=lambda s: (abs(int(s["difficulty"]) - (target_level + 1)), s["id"])
    )
    selected_scenarios = unseen_scenarios[: cfg.assessment_scenario_count]

    if (
        len(selected_qs) < cfg.assessment_question_count
        or len(selected_scenarios) < cfg.assessment_scenario_count
    ):
        raise ValidationDomainError(
            "INSUFFICIENT_UNSEEN_ITEMS",
            f"Need {cfg.assessment_question_count} unseen questions and "
            f"{cfg.assessment_scenario_count} unseen scenarios.",
        )

    items_public: list[dict[str, Any]] = []
    item_specs: list[dict[str, Any]] = []

    for q in selected_qs:
        items_public.append(
            {
                "item_id": q["id"],
                "item_type": AttemptItemType.QUESTION.value,
                "prompt": {
                    "id": q["id"],
                    "skill_area": q["skill_area"],
                    "difficulty": q["difficulty"],
                    "text": q["text"],
                    "options": shuffle_options_for_question(q["id"], q["options"]),
                    "data_origin": q.get("data_origin", "synthetic"),
                },
            }
        )
        item_specs.append(
            {
                "item_id": q["id"],
                "item_type": AttemptItemType.QUESTION.value,
                "skill_area": q["skill_area"],
                "difficulty": int(q["difficulty"]),
            }
        )

    for sc in selected_scenarios:
        _, series_origin = scenario_outcome(sc, cfg=cfg)
        pub = build_public_scenario(sc, series_data_origin=series_origin)
        items_public.append(
            {
                "item_id": sc["id"],
                "item_type": AttemptItemType.SCENARIO.value,
                "prompt": pub,
            }
        )
        item_specs.append(
            {
                "item_id": sc["id"],
                "item_type": AttemptItemType.SCENARIO.value,
                "skill_area": SkillArea.JUDGING_INFO.value,
                "difficulty": int(sc["difficulty"]),
            }
        )

    assessment_id = f"asmt_{uuid.uuid4().hex[:16]}"
    repo.create_session(
        session_id=assessment_id,
        user_id=user_id,
        session_type="assessment",
        target_level=int(target_level),
        state={"items": item_specs},
    )
    return {
        "assessment_id": assessment_id,
        "level": int(target_level),
        "items": items_public,
        "data_origin": aggregate_data_origin(
            [item["prompt"].get("data_origin", "synthetic") for item in items_public],
            empty_default="synthetic",
        ),
    }


def submit_assessment(
    repo: EducationRepository,
    user_id: str,
    assessment_id: str,
    answers: list[dict[str, Any]],
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Grades an assessment: pass = >=70% correct AND Brier <= 0.25.

    On pass: promotes user level, grants new unlocks, builds next-level plan.
    On fail: records updated skill scores and refreshes learning plan targeting weakest skills.
    """
    session = repo.get_session(assessment_id)
    if not session or session["session_type"] != "assessment":
        raise NotFoundError(
            "ASSESSMENT_NOT_FOUND", f"Assessment '{assessment_id}' not found."
        )
    if session["user_id"] != user_id:
        raise NotFoundError(
            "ASSESSMENT_NOT_FOUND", "Assessment does not belong to current user."
        )
    if session["completed"]:
        raise ValidationDomainError(
            "ASSESSMENT_ALREADY_SUBMITTED", "Assessment was already submitted."
        )

    # A stored target is never trusted beyond the learner's persisted level; a session
    # whose target exceeds it is stale/tampered and must not promote (or skip) any level.
    stored_level = repo.get_user_level(user_id, default_level=1)
    session_target = int(session["target_level"] or stored_level)
    if session_target > stored_level:
        raise ValidationDomainError(
            "ASSESSMENT_LEVEL_CHANGED",
            "This assessment no longer matches your current level. Start a new one.",
        )

    spec_map = {item["item_id"]: item for item in session["state"]["items"]}
    if len(answers) != len(spec_map):
        raise ValidationDomainError(
            "INCOMPLETE_SUBMISSION",
            f"Expected {len(spec_map)} answers, received {len(answers)}.",
        )
    submitted_ids = [str(answer.get("item_id", "")) for answer in answers]
    if len(set(submitted_ids)) != len(submitted_ids):
        raise ValidationDomainError(
            "DUPLICATE_ITEM", "Each assessment item must be answered exactly once."
        )
    if set(submitted_ids) != set(spec_map):
        raise ValidationDomainError(
            "INVALID_SUBMISSION_ITEMS",
            "Answers must match the items issued for this assessment.",
        )

    # Claim the session atomically before any attempt is recorded so concurrent submits
    # cannot both grade/promote. Released again if grading fails part-way.
    if not _claim_session(repo, assessment_id):
        raise ValidationDomainError(
            "ASSESSMENT_ALREADY_SUBMITTED", "Assessment was already submitted."
        )
    try:
        return _grade_and_apply(
            repo, user_id, assessment_id, session, spec_map, answers, stored_level, cfg
        )
    except Exception:
        _release_session(repo, assessment_id)
        raise


def _grade_and_apply(
    repo: EducationRepository,
    user_id: str,
    assessment_id: str,
    session: dict[str, Any],
    spec_map: dict[str, dict[str, Any]],
    answers: list[dict[str, Any]],
    stored_level: int,
    cfg: EducationConfig,
) -> dict[str, Any]:
    session_target = int(session["target_level"] or stored_level)
    graded_records: list[dict[str, Any]] = []
    brier_pairs: list[tuple[int, bool]] = []
    item_origins: list[str] = []
    correct_count = 0

    for ans in answers:
        item_id = ans["item_id"]
        spec = spec_map.get(item_id)
        if not spec:
            raise ValidationDomainError(
                "UNKNOWN_ITEM", f"Item '{item_id}' is not part of this assessment."
            )
        conf = int(ans["confidence"])
        user_ans = str(ans["answer"]).strip()

        if spec["item_type"] == AttemptItemType.QUESTION.value:
            q = repo.get_question(item_id)
            if not q:
                raise NotFoundError(
                    "QUESTION_NOT_FOUND", f"Question '{item_id}' missing."
                )
            item_origins.append(str(q.get("data_origin", "synthetic")))
            is_correct = user_ans == str(q["answer"]).strip()
        else:
            sc = repo.get_scenario(item_id)
            if not sc:
                raise NotFoundError(
                    "SCENARIO_NOT_FOUND", f"Scenario '{item_id}' missing."
                )
            outcome, sc_origin = scenario_outcome(sc, cfg=cfg)
            item_origins.append(sc_origin)
            is_correct = user_ans.lower() == outcome["actual_direction"]

        if is_correct:
            correct_count += 1

        repo.record_attempt(
            user_id=user_id,
            item_type=spec["item_type"],
            item_id=item_id,
            answer=user_ans,
            confidence=conf,
            correct=is_correct,
            context=AttemptContext.ASSESSMENT.value,
        )
        brier_pairs.append((conf, is_correct))
        graded_records.append(
            {
                "skill_area": spec["skill_area"],
                "difficulty": spec["difficulty"],
                "correct": is_correct,
            }
        )

    score_ratio = correct_count / len(spec_map)
    score_pct = round(100.0 * score_ratio, 2)
    brier = compute_brier_score(brier_pairs)
    skills = compute_skill_scores(graded_records)
    repo.record_skill_scores(user_id, skills, brier)

    passed = (score_ratio >= cfg.assessment_pass_accuracy) and (
        brier <= cfg.assessment_max_brier
    )
    current_level = stored_level

    new_level = None
    newly_unlocked: list[str] = []

    if passed:
        # Only the assessment gating the current level promotes, and by exactly one level;
        # re-takes of lower levels never change the level.
        promoted = (
            min(cfg.max_level, current_level + 1)
            if session_target == current_level
            else current_level
        )
        if promoted > current_level:
            repo.set_user_level(user_id, promoted)
        new_level = promoted
        newly_unlocked = ensure_level_unlocks(repo, user_id, promoted)
        build_or_update_plan(
            repo, user_id, level=promoted, skill_scores=skills, preserve_completed=False
        )
    else:
        # Fail updates the learning plan to remediate weakest skills from the assessment
        build_or_update_plan(
            repo,
            user_id,
            level=current_level,
            skill_scores=skills,
            preserve_completed=True,
        )

    origin = aggregate_data_origin(item_origins, empty_default="synthetic")
    state = dict(session["state"])
    state["result"] = {
        "passed": passed,
        "score": score_pct,
        "brier": brier,
        "new_level": new_level,
        "unlocked": newly_unlocked,
        "data_origin": origin,
    }
    repo.update_session(assessment_id, state, completed=True)

    return {
        "passed": passed,
        "score": score_pct,
        "brier": brier,
        "new_level": new_level,
        "unlocked": newly_unlocked,
        "data_origin": origin,
    }
