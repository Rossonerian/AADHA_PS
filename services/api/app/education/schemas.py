"""Pydantic request/response schemas matching SoT Section 7 verbatim (v1 + v2 compatible)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .enums import DataOrigin, Direction, LessonStatus, SkillArea

# ---- Onboarding (Phase 2) ----


class QuestionPublic(BaseModel):
    id: str
    level: int
    skill_area: SkillArea
    difficulty: int
    text: str
    options: list[str]
    data_origin: DataOrigin = DataOrigin.SYNTHETIC


class OnboardingStartResponse(BaseModel):
    session_id: str
    question: QuestionPublic


class OnboardingAnswerRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    question_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    confidence: int = Field(..., ge=50, le=100)


class OnboardingResult(BaseModel):
    level: int = Field(..., ge=1, le=4)
    skills: dict[str, float]
    brier: float = Field(..., ge=0.0, le=1.0)


class OnboardingAnswerResponse(BaseModel):
    next_question: QuestionPublic | None = None
    result: OnboardingResult | None = None


# ---- Plan & Lessons (Phase 3) ----


class PlanLessonItem(BaseModel):
    id: str
    title: str
    status: LessonStatus
    minutes: int
    skill_area: SkillArea | None = None


class PlanResponse(BaseModel):
    level: int
    progress_pct: float
    lessons: list[PlanLessonItem]


class LessonSection(BaseModel):
    heading: str
    body: str
    takeaway: str | None = None


class LessonCheckQuestion(BaseModel):
    id: str
    text: str
    options: list[str]


class LessonDetailResponse(BaseModel):
    id: str
    title: str
    level: int
    skill_area: SkillArea
    minutes: int
    sections: list[LessonSection]
    check_questions: list[LessonCheckQuestion]
    data_origin: DataOrigin = DataOrigin.SYNTHETIC


class LessonCheckAnswerItem(BaseModel):
    question_id: str
    answer: str
    confidence: int = Field(default=75, ge=50, le=100)


class LessonCheckRequest(BaseModel):
    answers: list[LessonCheckAnswerItem] = Field(min_length=1)


class LessonCheckResponse(BaseModel):
    lesson_id: str
    passed: bool
    score_pct: float
    correct_count: int
    total_count: int
    plan_progress_pct: float
    feedback: list[dict[str, Any]]


# ---- Scenarios (Phase 5) ----


class ScenarioChartPoint(BaseModel):
    date: str
    close: float
    volume: int | None = None


class ScenarioContextPublic(BaseModel):
    company: str
    symbol: str
    disclaimer: str = (
        "Historical learning exercise only — not investment advice or a price prediction."
    )
    chart: list[ScenarioChartPoint]
    headlines: list[str]
    numbers: dict[str, Any]


class ScenarioNextResponse(BaseModel):
    id: str
    as_of_date: str
    window_days: int
    difficulty: int
    tags: list[str]
    context: ScenarioContextPublic
    data_origin: DataOrigin


class ScenarioAnswerRequest(BaseModel):
    direction: Direction
    confidence: int = Field(..., ge=50, le=100)
    clues: list[str] = Field(default_factory=list)


class ScenarioOutcomePublic(BaseModel):
    stock_pct: float
    index_pct: float
    relative_pct: float
    actual_direction: Direction


class ScenarioAnswerResponse(BaseModel):
    correct: bool
    outcome: ScenarioOutcomePublic
    key_clues: list[str]
    explanation: str
    data_origin: DataOrigin


# ---- Assessments (Phase 4) ----


class AssessmentItemPublic(BaseModel):
    item_id: str
    item_type: str  # "question" | "scenario"
    prompt: dict[str, Any]


class AssessmentStartResponse(BaseModel):
    assessment_id: str
    level: int
    items: list[AssessmentItemPublic]


class AssessmentAnswerInput(BaseModel):
    item_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    confidence: int = Field(..., ge=50, le=100)


class AssessmentSubmitRequest(BaseModel):
    answers: list[AssessmentAnswerInput] = Field(min_length=1)


class AssessmentSubmitResponse(BaseModel):
    passed: bool
    score: float
    brier: float
    new_level: int | None = None
    unlocked: list[str] = Field(default_factory=list)


# ---- Explain a Stock & Dashboard & Study Mode (Phase 6) ----


class ExplainEvent(BaseModel):
    text: str
    source: str


class ExplainMove(BaseModel):
    date: str
    pct: float
    events: list[ExplainEvent]


class ExplainStockResponse(BaseModel):
    symbol: str
    year: int
    chart: list[ScenarioChartPoint]
    moves: list[ExplainMove]
    summary: str
    data_origin: DataOrigin


class DashboardResponse(BaseModel):
    level: int
    unlocks: list[str]
    skills_over_time: list[dict[str, Any]]
    brier_over_time: list[dict[str, Any]]
    scenario_accuracy: list[dict[str, Any]]


class StudyStartRequest(BaseModel):
    context: str = Field(..., pattern="^(study_pre|study_post)$")


class StudyStartResponse(BaseModel):
    session_id: str
    context: str
    items: list[AssessmentItemPublic]


class StudySubmitRequest(BaseModel):
    answers: list[AssessmentAnswerInput] = Field(min_length=1)


class StudySubmitResponse(BaseModel):
    session_id: str
    context: str
    score_pct: float
    brier: float
    red_flag_accuracy_pct: float
    total_items: int
