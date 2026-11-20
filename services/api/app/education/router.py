"""FastAPI APIRouter implementing all Education endpoints per SoT Section 7."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ..core.auth import User, current_user
from ..core.db import get_db
from .assessments import start_assessment, submit_assessment
from .explain import (
    explain_stock,
    get_dashboard,
    start_study_session,
    submit_study_session,
)
from .learning import get_lesson_detail, get_plan, submit_lesson_check
from .onboarding import answer_onboarding, start_onboarding
from .repository import EducationRepository
from .scenarios import answer_scenario, get_next_scenario
from .schemas import (
    AssessmentStartResponse,
    AssessmentSubmitRequest,
    AssessmentSubmitResponse,
    DashboardResponse,
    ExplainStockResponse,
    LessonCheckRequest,
    LessonCheckResponse,
    LessonDetailResponse,
    OnboardingAnswerRequest,
    OnboardingAnswerResponse,
    OnboardingStartResponse,
    PlanResponse,
    ScenarioAnswerRequest,
    ScenarioAnswerResponse,
    ScenarioNextResponse,
    StudyStartRequest,
    StudyStartResponse,
    StudySubmitRequest,
    StudySubmitResponse,
)

router = APIRouter(tags=["education"])


def _repo(conn: Any = Depends(get_db)) -> EducationRepository:
    return EducationRepository(conn)


def _effective_level(repo: EducationRepository, user: User) -> int:
    """Uses persisted DB level if user exists in DB, otherwise falls back to auth token level."""
    return repo.get_user_level(user.id, default_level=user.level)


# ---- Phase 2: Onboarding ----


@router.post("/onboarding/start", response_model=OnboardingStartResponse)
def api_onboarding_start(
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    return start_onboarding(repo, user_id=user.id, user_name=user.name)


@router.post("/onboarding/answer", response_model=OnboardingAnswerResponse)
def api_onboarding_answer(
    body: OnboardingAnswerRequest,
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    return answer_onboarding(
        repo,
        user_id=user.id,
        session_id=body.session_id,
        question_id=body.question_id,
        answer=body.answer,
        confidence=body.confidence,
    )


# ---- Phase 3: Plan & Lessons ----


@router.get("/plan", response_model=PlanResponse)
def api_get_plan(
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    lvl = _effective_level(repo, user)
    return get_plan(repo, user_id=user.id, user_level=lvl)


@router.get("/lessons/{lesson_id}", response_model=LessonDetailResponse)
def api_get_lesson(
    lesson_id: str,
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    _ = user  # Auth enforced
    return get_lesson_detail(repo, lesson_id=lesson_id)


@router.post("/lessons/{lesson_id}/check", response_model=LessonCheckResponse)
def api_submit_lesson_check(
    lesson_id: str,
    body: LessonCheckRequest,
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    return submit_lesson_check(
        repo,
        user_id=user.id,
        lesson_id=lesson_id,
        answers=[
            (a.model_dump() if hasattr(a, "model_dump") else a.dict())
            for a in body.answers
        ],
    )


# ---- Phase 5: Historical Scenarios ----


@router.get("/scenarios/next", response_model=ScenarioNextResponse)
def api_scenarios_next(
    difficulty: int | None = Query(default=None, ge=1, le=5),
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    lvl = _effective_level(repo, user)
    return get_next_scenario(
        repo, user_id=user.id, user_level=lvl, difficulty=difficulty
    )


@router.post("/scenarios/{scenario_id}/answer", response_model=ScenarioAnswerResponse)
def api_scenarios_answer(
    scenario_id: str,
    body: ScenarioAnswerRequest,
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    lvl = _effective_level(repo, user)
    return answer_scenario(
        repo,
        user_id=user.id,
        user_level=lvl,
        scenario_id=scenario_id,
        direction=body.direction.value,
        confidence=body.confidence,
        clues=body.clues,
    )


# ---- Phase 4: Level-Up Assessments ----


@router.post("/assessments/{level}/start", response_model=AssessmentStartResponse)
def api_assessments_start(
    level: int,
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    _effective_level(repo, user)
    return start_assessment(repo, user_id=user.id, target_level=level)


@router.post(
    "/assessments/{assessment_id}/submit", response_model=AssessmentSubmitResponse
)
def api_assessments_submit(
    assessment_id: str,
    body: AssessmentSubmitRequest,
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    return submit_assessment(
        repo,
        user_id=user.id,
        assessment_id=assessment_id,
        answers=[
            (a.model_dump() if hasattr(a, "model_dump") else a.dict())
            for a in body.answers
        ],
    )


# ---- Phase 6: Explain a Stock, Dashboard & Study Mode ----


@router.get("/explain", response_model=ExplainStockResponse)
def api_explain_stock(
    symbol: str = Query(
        ..., min_length=1, max_length=40, pattern=r"^[A-Za-z0-9 &.\-]+$"
    ),
    year: int = Query(..., ge=2005, le=2030),
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    lvl = _effective_level(repo, user)
    return explain_stock(
        repo, user_id=user.id, user_level=lvl, symbol=symbol, year=year
    )


@router.get("/me/dashboard", response_model=DashboardResponse)
def api_me_dashboard(
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    lvl = _effective_level(repo, user)
    return get_dashboard(repo, user_id=user.id, user_level=lvl)


@router.post("/study/start", response_model=StudyStartResponse)
def api_study_start(
    body: StudyStartRequest,
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    _effective_level(repo, user)
    return start_study_session(repo, user_id=user.id, context=body.context)


@router.post("/study/{session_id}/submit", response_model=StudySubmitResponse)
def api_study_submit(
    session_id: str,
    body: StudySubmitRequest,
    user: User = Depends(current_user),
    repo: EducationRepository = Depends(_repo),
) -> dict[str, Any]:
    return submit_study_session(
        repo,
        user_id=user.id,
        session_id=session_id,
        answers=[
            (a.model_dump() if hasattr(a, "model_dump") else a.dict())
            for a in body.answers
        ],
    )
