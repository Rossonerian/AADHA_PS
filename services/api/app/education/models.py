"""SQLAlchemy 2.0 ORM models for PaisaProof Education tables (SoT Section 6).

Designed for Supabase Postgres (SQLAlchemy 2.0 + Alembic).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Unlock(Base):
    __tablename__ = "unlocks"
    __table_args__ = (
        UniqueConstraint("user_id", "tool", name="uq_unlocks_user_tool"),
        CheckConstraint(
            "tool IN ('scenarios','red_flag_check','explain_stock','verifier','dashboard')",
            name="ck_unlocks_tool",
        ),
        Index("ix_unlocks_user_id", "user_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tool: Mapped[str] = mapped_column(String(32), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SkillScore(Base):
    __tablename__ = "skill_scores"
    __table_args__ = (
        CheckConstraint(
            "skill_area IN ('basics','reading_stock','judging_info','risk')",
            name="ck_skill_scores_area",
        ),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_skill_scores_range"),
        CheckConstraint("brier >= 0 AND brier <= 1", name="ck_skill_scores_brier"),
        Index("ix_skill_scores_user_measured", "user_id", "measured_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill_area: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    brier: Mapped[float] = mapped_column(Float, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 4", name="ck_questions_level"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_questions_difficulty"),
        CheckConstraint(
            "skill_area IN ('basics','reading_stock','judging_info','risk')",
            name="ck_questions_skill_area",
        ),
        CheckConstraint(
            "data_origin IN ('real','synthetic')", name="ck_questions_origin"
        ),
        Index("ix_questions_level_skill_diff", "level", "skill_area", "difficulty"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_area: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    answer: Mapped[str] = mapped_column(String(256), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    data_origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default="synthetic"
    )


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('question','scenario','verifier_guess')",
            name="ck_attempts_item_type",
        ),
        CheckConstraint("confidence BETWEEN 50 AND 100", name="ck_attempts_confidence"),
        CheckConstraint(
            "context IN ('onboarding','lesson','assessment','practice','study_pre','study_post')",
            name="ck_attempts_context",
        ),
        Index("ix_attempts_user_context", "user_id", "context", "created_at"),
        Index("ix_attempts_user_item", "user_id", "item_type", "item_id"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    context: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 4", name="ck_lessons_level"),
        CheckConstraint(
            "skill_area IN ('basics','reading_stock','judging_info','risk')",
            name="ck_lessons_skill_area",
        ),
        CheckConstraint("minutes BETWEEN 1 AND 60", name="ck_lessons_minutes"),
        CheckConstraint(
            "data_origin IN ('real','synthetic')", name="ck_lessons_origin"
        ),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_area: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sections: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    check_questions: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    data_origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default="synthetic"
    )


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_plans_user_id"),
        CheckConstraint("level BETWEEN 1 AND 4", name="ck_plans_level"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lesson_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    progress: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_scenarios_difficulty"),
        CheckConstraint("window_days > 0", name="ck_scenarios_window_days"),
        CheckConstraint(
            "data_origin IN ('real','synthetic')", name="ck_scenarios_origin"
        ),
        Index("ix_scenarios_difficulty", "difficulty"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, nullable=False)
    outcome: Mapped[dict] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    key_clues: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(16), nullable=False)


class User(Base):
    """Reference to Hardhik's users table (for tests or foreign key resolution)."""

    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="Learner")
    current_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EduSession(Base):
    __tablename__ = "edu_sessions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExplainCache(Base):
    __tablename__ = "edu_explain_cache"
    __table_args__ = (
        UniqueConstraint("symbol", "year", name="uq_explain_symbol_year"),
        CheckConstraint(
            "data_origin IN ('real','synthetic')", name="ck_explain_origin"
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    chart: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    moves: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(16), nullable=False)
