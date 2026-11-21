"""SQLAlchemy ORM model for extended user profile and onboarding state."""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class UserProfileRecord(Base):
    """Per-user onboarding and learning preference profile (1:1 with `users`)."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            "goal IS NULL OR goal IN ('learn_basics', 'avoid_scams', 'invest_smarter', 'other')",
            name="ck_user_profiles_goal",
        ),
        CheckConstraint(
            "experience IS NULL OR experience IN ('new', 'some', 'experienced')",
            name="ck_user_profiles_experience",
        ),
        CheckConstraint(
            "weekly_minutes IS NULL OR (weekly_minutes >= 1 AND weekly_minutes <= 10080)",
            name="ck_user_profiles_weekly_minutes",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        unique=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
        server_default="",
    )
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(32), nullable=True)
    weekly_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )
