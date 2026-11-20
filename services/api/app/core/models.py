"""Core platform SQLAlchemy models owned by Hardhik."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRecord(Base):
    """Registered user profile and current mastery level (1–4)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "current_level >= 1 AND current_level <= 4",
            name="ck_users_current_level_range",
        ),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", server_default=""
    )
    current_level: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class JobRunRecord(Base):
    """Observability record for scheduled market refresh and claim scoring runs."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    market_data_as_of: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        server_default="{}",
    )
    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
