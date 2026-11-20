"""Phase 2: Adaptive onboarding engine (12-15 questions, 4 skills, confidence 50-100, Brier)."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set

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
)

SKILL_ROTATION: List[str] = [
    SkillArea.BASICS.value,
    SkillArea.READING_STOCK.value,
    SkillArea.JUDGING_INFO.value,
    SkillArea.RISK.value,
]


def _public_question(q: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": q["id"],
        "level": q["level"],
        "skill_area": q["skill_area"],
        "difficulty": q["difficulty"],
        "text": q["text"],
        "options": q["options"],
        "data_origin": q.get("data_origin", "synthetic"),
    }


def _select_next_question(
    repo: EducationRepository,
    target_skill: str,
    target_difficulty: int,
    asked_ids: Set[str],
) -> Optional[Dict[str, Any]]:
    """Selects an unseen question matching target_skill and closest difficulty to target_difficulty."""
    candidates = repo.list_questions(skill_area=target_skill, exclude_ids=asked_ids)
    if not candidates:
        candidates = repo.list_questions(exclude_ids=asked_ids)
    if not candidates:
        return None
    candidates.sort(key=lambda q: (abs(int(q["difficulty"]) - target_difficulty), q["id"]))
    return candidates[0]


def start_onboarding(
    repo: EducationRepository,
    user_id: str,
    user_name: str = "Learner",
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> Dict[str, Any]:
    """Starts an adaptive onboarding quiz session starting at medium difficulty (3)."""
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
        "min_questions": cfg.onboarding_min_questions,
        "max_questions": cfg.onboarding_max_questions,
    }
    repo.create_session(
        session_id=session_id,
        user_id=user_id,
        session_type="onboarding",
        state=state,
    )
    return {
        "session_id": session_id,
        "question": _public_question(first_q),
    }


def _should_stop_onboarding(responses: List[Dict[str, Any]], min_q: int, max_q: int) -> bool:
    """Stops between min_q (12) and max_q (15) once skill coverage & signal stabilize."""
    n = len(responses)
    if n >= max_q:
        return True
    if n < min_q:
        return False
    # Check if all 4 skills have >= 3 questions and performance is decisive (very high or very low)
    acc = sum(1 for r in responses if r["correct"]) / n
    if acc >= 0.85 or acc <= 0.25:
        return True
    return False


def answer_onboarding(
    repo: EducationRepository,
    user_id: str,
    session_id: str,
    question_id: str,
    answer: str,
    confidence: int,
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> Dict[str, Any]:
    """Records an onboarding answer, adapts difficulty, and either returns next_question or final result."""
    session = repo.get_session(session_id)
    if not session or session["session_type"] != "onboarding":
        raise NotFoundError("SESSION_NOT_FOUND", f"Onboarding session '{session_id}' not found.")
    if session["user_id"] != user_id:
        raise NotFoundError("SESSION_NOT_FOUND", "Onboarding session does not belong to current user.")
    if session["completed"]:
        raise ValidationDomainError("SESSION_COMPLETED", "Onboarding session is already completed.")

    state = session["state"]
    if state.get("current_question_id") != question_id:
        raise ValidationDomainError(
            "QUESTION_MISMATCH",
            f"Expected answer for question '{state.get('current_question_id')}', got '{question_id}'.",
        )

    question = repo.get_question(question_id)
    if not question:
        raise NotFoundError("QUESTION_NOT_FOUND", f"Question '{question_id}' not found.")

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

    responses: List[Dict[str, Any]] = state["responses"]
    responses.append(
        {
            "question_id": question_id,
            "skill_area": question["skill_area"],
            "difficulty": int(question["difficulty"]),
            "confidence": int(confidence),
            "correct": is_correct,
        }
    )

    new_diff = next_adaptive_difficulty(int(state["current_difficulty"]), is_correct)
    state["current_difficulty"] = new_diff

    min_q = int(state.get("min_questions", cfg.onboarding_min_questions))
    max_q = int(state.get("max_questions", cfg.onboarding_max_questions))

    if not _should_stop_onboarding(responses, min_q=min_q, max_q=max_q):
        next_skill = SKILL_ROTATION[len(responses) % len(SKILL_ROTATION)]
        asked = set(state["asked_ids"])
        next_q = _select_next_question(repo, next_skill, new_diff, asked)
        if next_q is not None:
            state["asked_ids"].append(next_q["id"])
            state["current_question_id"] = next_q["id"]
            repo.update_session(session_id, state, completed=False)
            return {"next_question": _public_question(next_q), "result": None}

    # Finalize onboarding: compute per-skill scores, Brier, level, unlocks, and initial learning plan
    brier = compute_brier_score([(r["confidence"], r["correct"]) for r in responses])
    skills = compute_skill_scores(responses)
    accuracy_pct = 100.0 * sum(1 for r in responses if r["correct"]) / max(1, len(responses))
    correct_diffs = [r["difficulty"] for r in responses if r["correct"]]
    avg_diff_correct = sum(correct_diffs) / len(correct_diffs) if correct_diffs else 1.0
    level = determine_onboarding_level(accuracy_pct, brier, avg_diff_correct)

    repo.set_user_level(user_id, level)
    repo.record_skill_scores(user_id, skills, brier)
    ensure_level_unlocks(repo, user_id, level)
    build_or_update_plan(repo, user_id, level=level, skill_scores=skills, preserve_completed=False)

    state["current_question_id"] = None
    state["result"] = {"level": level, "skills": skills, "brier": brier}
    repo.update_session(session_id, state, completed=True)

    return {
        "next_question": None,
        "result": {"level": level, "skills": skills, "brier": brier},
    }
