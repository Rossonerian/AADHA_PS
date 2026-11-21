"""Phase 2: Adaptive onboarding check-in (6 questions, 4 skills, confidence 50-100, Brier)."""

from __future__ import annotations

import uuid
from typing import Any

from ..core.provenance import aggregate_data_origin
from .config import DEFAULT_CONFIG, EducationConfig
from .enums import AttemptContext, AttemptItemType, SkillArea
from .exceptions import NotFoundError, ValidationDomainError
from .learning import build_or_update_plan, ensure_level_unlocks
from .repository import EducationRepository
from .scoring import (
    compute_brier_score,
    compute_skill_scores,
    determine_onboarding_level,
    next_adaptive_difficulty,
    shuffle_options_for_question,
)

SKILL_ROTATION: list[str] = [
    SkillArea.BASICS.value,
    SkillArea.READING_STOCK.value,
    SkillArea.JUDGING_INFO.value,
    SkillArea.RISK.value,
]


def _public_question(q: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": q["id"],
        "index": index,
        "number": index,
        "level": q["level"],
        "skill_area": q["skill_area"],
        "difficulty": q["difficulty"],
        "text": q["text"],
        "options": shuffle_options_for_question(q["id"], q["options"]),
        "data_origin": q.get("data_origin", "synthetic"),
    }


def _select_next_question(
    repo: EducationRepository,
    target_skill: str,
    target_difficulty: int,
    asked_ids: set[str],
) -> dict[str, Any] | None:
    """Selects an unseen question matching target_skill.

    Prefers the difficulty closest to target_difficulty.
    """
    candidates = repo.list_questions(skill_area=target_skill, exclude_ids=asked_ids)
    if not candidates:
        candidates = repo.list_questions(exclude_ids=asked_ids)
    if not candidates:
        return None
    candidates.sort(
        key=lambda q: (abs(int(q["difficulty"]) - target_difficulty), q["id"])
    )
    return candidates[0]


def start_onboarding(
    repo: EducationRepository,
    user_id: str,
    user_name: str = "Learner",
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Starts a 6-question adaptive check-in starting at medium difficulty (3)."""
    repo.ensure_user(user_id, name=user_name)
    first_skill = SKILL_ROTATION[0]
    first_q = _select_next_question(
        repo,
        target_skill=first_skill,
        target_difficulty=cfg.onboarding_start_difficulty,
        asked_ids=set(),
    )
    if not first_q:
        raise ValidationDomainError(
            "QUESTION_BANK_EMPTY",
            "Question bank has no available questions for onboarding.",
        )

    session_id = f"onb_{uuid.uuid4().hex[:16]}"
    state = {
        "current_difficulty": cfg.onboarding_start_difficulty,
        "asked_ids": [first_q["id"]],
        "current_question_id": first_q["id"],
        "responses": [],
        "total_questions": cfg.onboarding_question_count,
    }
    repo.create_session(
        session_id=session_id,
        user_id=user_id,
        session_type="onboarding",
        state=state,
    )
    return {
        "session_id": session_id,
        "total_questions": cfg.onboarding_question_count,
        "question": _public_question(first_q, index=1),
        "data_origin": aggregate_data_origin(
            [first_q.get("data_origin", "synthetic")], empty_default="synthetic"
        ),
    }


def _should_stop_onboarding(responses: list[dict[str, Any]], total_q: int) -> bool:
    """The check-in ends after exactly ``total_q`` answers, with no other gate.

    Skill balance is handled by round-robin question selection, not by a
    stop rule, so a lopsided run can never keep the check-in going.
    """
    return len(responses) >= total_q


def answer_onboarding(
    repo: EducationRepository,
    user_id: str,
    session_id: str,
    question_id: str,
    answer: str,
    confidence: int,
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Records an onboarding answer and adapts difficulty.

    Returns either the next_question or the final result.
    """
    session = repo.get_session(session_id)
    if not session or session["session_type"] != "onboarding":
        raise NotFoundError(
            "SESSION_NOT_FOUND", f"Onboarding session '{session_id}' not found."
        )
    if session["user_id"] != user_id:
        raise NotFoundError(
            "SESSION_NOT_FOUND", "Onboarding session does not belong to current user."
        )
    if session["completed"]:
        raise ValidationDomainError(
            "SESSION_COMPLETED", "Onboarding session is already completed."
        )
    # Always the configured count, even for sessions created before a change.
    total_q = cfg.onboarding_question_count

    state = session["state"]
    if state.get("current_question_id") != question_id:
        raise ValidationDomainError(
            "QUESTION_MISMATCH",
            f"Expected answer for question '{state.get('current_question_id')}', "
            f"got '{question_id}'.",
        )

    question = repo.get_question(question_id)
    if not question:
        raise NotFoundError(
            "QUESTION_NOT_FOUND", f"Question '{question_id}' not found."
        )

    is_correct = str(answer).strip() == str(question["answer"]).strip()
    repo.record_attempt(
        user_id=user_id,
        item_type=AttemptItemType.QUESTION.value,
        item_id=question_id,
        answer=answer,
        confidence=confidence,
        correct=is_correct,
        context=AttemptContext.ONBOARDING.value,
    )

    responses: list[dict[str, Any]] = state["responses"]
    responses.append(
        {
            "question_id": question_id,
            "skill_area": question["skill_area"],
            "difficulty": int(question["difficulty"]),
            "confidence": int(confidence),
            "correct": is_correct,
            "data_origin": question.get("data_origin", "synthetic"),
        }
    )

    new_diff = next_adaptive_difficulty(int(state["current_difficulty"]), is_correct)
    state["current_difficulty"] = new_diff

    response_origins = [r.get("data_origin", "synthetic") for r in responses]
    if not _should_stop_onboarding(responses, total_q=total_q):
        next_skill = SKILL_ROTATION[len(responses) % len(SKILL_ROTATION)]
        asked = set(state["asked_ids"])
        next_q = _select_next_question(repo, next_skill, new_diff, asked)
        if next_q is not None:
            state["asked_ids"].append(next_q["id"])
            state["current_question_id"] = next_q["id"]
            repo.update_session(session_id, state, completed=False)
            return {
                "total_questions": total_q,
                "next_question": _public_question(next_q, index=len(responses) + 1),
                "result": None,
                "data_origin": aggregate_data_origin(
                    [*response_origins, next_q.get("data_origin", "synthetic")],
                    empty_default="synthetic",
                ),
            }

    # Finalize onboarding: compute per-skill scores, Brier, level, unlocks,
    # and initial learning plan
    brier = compute_brier_score([(r["confidence"], r["correct"]) for r in responses])
    skills = compute_skill_scores(responses)
    accuracy_pct = (
        100.0 * sum(1 for r in responses if r["correct"]) / max(1, len(responses))
    )
    correct_diffs = [r["difficulty"] for r in responses if r["correct"]]
    avg_diff_correct = sum(correct_diffs) / len(correct_diffs) if correct_diffs else 1.0
    measured = determine_onboarding_level(accuracy_pct, brier, avg_diff_correct)
    # Retakes are allowed but never demote a learner or reset lesson progress.
    level = max(repo.get_user_level(user_id, default_level=1), measured)

    repo.set_user_level(user_id, level)
    repo.record_skill_scores(user_id, skills, brier)
    ensure_level_unlocks(repo, user_id, level)
    build_or_update_plan(
        repo, user_id, level=level, skill_scores=skills, preserve_completed=True
    )

    state["current_question_id"] = None
    state["result"] = {"level": level, "skills": skills, "brier": brier}
    repo.update_session(session_id, state, completed=True)

    return {
        "total_questions": total_q,
        "next_question": None,
        "result": {"level": level, "skills": skills, "brier": brier},
        "data_origin": aggregate_data_origin(
            response_origins, empty_default="synthetic"
        ),
    }
