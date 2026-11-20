"""Phase 3: Levels, tool unlocks, weakest-skill learning plan, and micro-lessons."""

from __future__ import annotations

from typing import Any

from ..core import guardrails
from .enums import (
    TOOL_REQUIRED_LEVEL,
    AttemptContext,
    AttemptItemType,
    LessonStatus,
    SkillArea,
    ToolName,
    cumulative_unlocks_for_level,
)
from .exceptions import NotFoundError, ToolLockedError, ValidationDomainError
from .repository import EducationRepository


def get_user_unlocks(
    repo: EducationRepository, user_id: str, user_level: int | None = None
) -> list[str]:
    """Public helper exposed for Hardhik's GET /me endpoint.

    Ensures the user has at least their level's cumulative unlocks and returns them
    in canonical order.
    """
    level = (
        user_level
        if user_level is not None
        else repo.get_user_level(user_id, default_level=1)
    )
    required = cumulative_unlocks_for_level(level)
    repo.grant_unlocks(user_id, required)
    return repo.list_unlocks(user_id)


def ensure_level_unlocks(
    repo: EducationRepository, user_id: str, level: int
) -> list[str]:
    """Grants all cumulative unlocks for `level` and returns newly granted tools."""
    tools = cumulative_unlocks_for_level(level)
    return repo.grant_unlocks(user_id, tools)


def require_tool_unlocked(
    repo: EducationRepository,
    user_id: str,
    tool: ToolName,
    user_level: int | None = None,
) -> None:
    """Enforces SoT Section 8 tool unlocks.

    Raises ToolLockedError (HTTP 403 TOOL_LOCKED) if the tool is locked.
    """
    level = (
        user_level
        if user_level is not None
        else repo.get_user_level(user_id, default_level=1)
    )
    required_level = TOOL_REQUIRED_LEVEL[tool]
    unlocked = set(get_user_unlocks(repo, user_id, user_level=level))
    if tool.value not in unlocked or level < required_level:
        raise ToolLockedError(
            tool=tool.value, required_level=required_level, current_level=level
        )


def build_or_update_plan(
    repo: EducationRepository,
    user_id: str,
    level: int | None = None,
    skill_scores: dict[str, float] | None = None,
    preserve_completed: bool = True,
) -> dict[str, Any]:
    """Builds a personalised learning plan prioritizing the user's weakest skill areas first."""
    lvl = level if level is not None else repo.get_user_level(user_id, default_level=1)
    scores = (
        skill_scores
        if skill_scores is not None
        else repo.get_latest_skill_scores(user_id)
    )

    # Order skill areas from weakest to strongest (default 50.0 if unmeasured)
    ordered_skills = sorted(
        [s.value for s in SkillArea],
        key=lambda area: (scores.get(area, 50.0), area),
    )

    # Lessons exist for L1-L3; Level 4 users receive Level 3 mastery refreshers
    # ordered by weakest skill
    plan_lesson_level = min(3, max(1, lvl))
    level_lessons = repo.list_lessons(level=plan_lesson_level)
    if not level_lessons:
        level_lessons = repo.list_lessons()

    skill_rank = {area: idx for idx, area in enumerate(ordered_skills)}
    level_lessons.sort(
        key=lambda lsn: (skill_rank.get(lsn["skill_area"], 99), lsn["id"])
    )
    lesson_ids = [lsn["id"] for lsn in level_lessons]

    existing_plan = repo.get_plan(user_id)
    existing_progress = (
        existing_plan["progress"] if (existing_plan and preserve_completed) else {}
    )
    progress: dict[str, str] = {
        lid: existing_progress.get(lid, LessonStatus.NOT_STARTED.value)
        for lid in lesson_ids
    }
    repo.upsert_plan(
        user_id=user_id, level=lvl, lesson_ids=lesson_ids, progress=progress
    )
    return get_plan(repo, user_id, user_level=lvl)


def get_plan(
    repo: EducationRepository, user_id: str, user_level: int | None = None
) -> dict[str, Any]:
    """Returns GET /plan response payload, auto-generating a weakest-skill plan if none exists."""
    lvl = (
        user_level
        if user_level is not None
        else repo.get_user_level(user_id, default_level=1)
    )
    plan = repo.get_plan(user_id)
    if not plan:
        return build_or_update_plan(repo, user_id, level=lvl)

    lessons_out: list[dict[str, Any]] = []
    completed = 0
    for lid in plan["lesson_ids"]:
        lesson = repo.get_lesson(lid)
        if not lesson:
            continue
        status = plan["progress"].get(lid, LessonStatus.NOT_STARTED.value)
        if status == LessonStatus.COMPLETED.value:
            completed += 1
        lessons_out.append(
            {
                "id": lesson["id"],
                "title": lesson["title"],
                "status": status,
                "minutes": lesson["minutes"],
                "skill_area": lesson["skill_area"],
            }
        )
    total = len(lessons_out)
    progress_pct = round(100.0 * completed / total, 1) if total > 0 else 0.0
    return {
        "level": plan["level"],
        "progress_pct": progress_pct,
        "lessons": lessons_out,
    }


def get_lesson_detail(repo: EducationRepository, lesson_id: str) -> dict[str, Any]:
    """Returns GET /lessons/{id} response with guardrailed sections and public check questions."""
    lesson = repo.get_lesson(lesson_id)
    if not lesson:
        raise NotFoundError("LESSON_NOT_FOUND", f"Lesson '{lesson_id}' does not exist.")

    safe_sections = []
    for sec in lesson["sections"]:
        safe_body = guardrails.check_output(sec["body"]).text
        safe_takeaway = (
            guardrails.check_output(sec["takeaway"]).text
            if sec.get("takeaway")
            else None
        )
        safe_sections.append(
            {
                "heading": sec["heading"],
                "body": safe_body,
                "takeaway": safe_takeaway,
            }
        )

    public_checks = [
        {"id": cq["id"], "text": cq["text"], "options": cq["options"]}
        for cq in lesson["check_questions"]
    ]
    return {
        "id": lesson["id"],
        "title": lesson["title"],
        "level": lesson["level"],
        "skill_area": lesson["skill_area"],
        "minutes": lesson["minutes"],
        "sections": safe_sections,
        "check_questions": public_checks,
        "data_origin": lesson.get("data_origin", "synthetic"),
    }


def submit_lesson_check(
    repo: EducationRepository,
    user_id: str,
    lesson_id: str,
    answers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Grades lesson check questions and updates plan progress.

    Records attempts with context='lesson'.
    """
    lesson = repo.get_lesson(lesson_id)
    if not lesson:
        raise NotFoundError("LESSON_NOT_FOUND", f"Lesson '{lesson_id}' does not exist.")

    cq_map = {cq["id"]: cq for cq in lesson["check_questions"]}
    if len(answers) != len(cq_map):
        raise ValidationDomainError(
            "INCOMPLETE_SUBMISSION", f"Expected {len(cq_map)} lesson answers."
        )
    submitted_ids = [str(answer.get("question_id", "")) for answer in answers]
    if len(set(submitted_ids)) != len(submitted_ids):
        raise ValidationDomainError(
            "DUPLICATE_ITEM", "Each lesson question must be answered exactly once."
        )
    if set(submitted_ids) != set(cq_map):
        raise ValidationDomainError(
            "INVALID_SUBMISSION_ITEMS",
            "Answers must match the questions issued for this lesson.",
        )
    correct_count = 0
    feedback: list[dict[str, Any]] = []

    for ans in answers:
        qid = ans["question_id"]
        cq = cq_map.get(qid)
        if not cq:
            raise NotFoundError(
                "CHECK_QUESTION_NOT_FOUND",
                f"Check question '{qid}' not in lesson '{lesson_id}'.",
            )
        is_correct = str(ans["answer"]).strip() == str(cq["answer"]).strip()
        if is_correct:
            correct_count += 1
        repo.record_attempt(
            user_id=user_id,
            item_type=AttemptItemType.QUESTION.value,
            item_id=qid,
            answer=str(ans["answer"]),
            confidence=int(ans.get("confidence", 75)),
            correct=is_correct,
            context=AttemptContext.LESSON.value,
        )
        feedback.append(
            {
                "question_id": qid,
                "correct": is_correct,
                "explanation": guardrails.check_output(cq.get("explanation", "")).text,
            }
        )

    total = len(cq_map)
    score_pct = round(100.0 * correct_count / total, 1) if total > 0 else 0.0
    passed = (
        score_pct >= 66.0
    )  # >= 2/3 check questions correct completes the micro-lesson

    plan = repo.get_plan(user_id)
    if not plan:
        build_or_update_plan(repo, user_id)
        plan = repo.get_plan(user_id)

    if plan:
        progress = dict(plan["progress"])
        progress[lesson_id] = (
            LessonStatus.COMPLETED.value if passed else LessonStatus.IN_PROGRESS.value
        )
        if lesson_id not in plan["lesson_ids"]:
            plan["lesson_ids"].append(lesson_id)
        repo.upsert_plan(user_id, plan["level"], plan["lesson_ids"], progress)

    updated_plan = get_plan(repo, user_id)
    return {
        "lesson_id": lesson_id,
        "passed": passed,
        "score_pct": score_pct,
        "correct_count": correct_count,
        "total_count": total,
        "plan_progress_pct": updated_plan["progress_pct"],
        "feedback": feedback,
    }
