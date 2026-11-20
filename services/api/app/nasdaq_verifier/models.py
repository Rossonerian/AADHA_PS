"""Durable, private answer keys shared by all API instances."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class NasdaqChallenge(Base):
    __tablename__ = "nasdaq_challenges"
    __table_args__ = (
        CheckConstraint("data_origin = 'real'", name="ck_nasdaq_challenges_origin"),
        Index("ix_nasdaq_challenges_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(66), primary_key=True)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    answers: Mapped[dict[str, str]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(String(9), default="real")
