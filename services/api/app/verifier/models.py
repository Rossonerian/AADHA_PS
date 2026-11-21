"""Verifier persistence. The platform owns the users table and session lifecycle."""

from datetime import date, datetime
from uuid import UUID, uuid4

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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import UserRecord


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint(
            "platform", "handle", "data_origin", name="uq_sources_identity"
        ),
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_sources_score"),
        CheckConstraint("scored_claims >= 0", name="ck_sources_scored_claims"),
        CheckConstraint(
            "data_origin IN ('real', 'synthetic')", name="ck_sources_origin"
        ),
        CheckConstraint(
            "label IN ('reliable', 'semi_reliable', 'not_reliable', 'not_enough_history')",
            name="ck_sources_label",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String(32))
    handle: Mapped[str] = mapped_column(String(255))
    sebi_reg_no: Mapped[str | None] = mapped_column(String(32))
    sebi_registered: Mapped[bool | None] = mapped_column(Boolean)
    enforcement_flag: Mapped[bool | None] = mapped_column(Boolean)
    enforcement_refs: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    score: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(24), default="not_enough_history")
    scored_claims: Mapped[int] = mapped_column(Integer, default=0)
    data_origin: Mapped[str] = mapped_column(String(9))


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_submissions_user_content"),
        CheckConstraint(
            "data_origin IN ('real', 'synthetic')", name="ck_submissions_origin"
        ),
        CheckConstraint(
            "user_confidence BETWEEN 50 AND 100", name="ck_submissions_confidence"
        ),
        Index("ix_submissions_user_capture", "user_id", "captured_at"),
        Index("ix_submissions_source", "source_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey(UserRecord.id, name="fk_submissions_user_id_users")
    )
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id"))
    transcript_segments: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    raw_content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post_url: Mapped[str | None] = mapped_column(String(2048))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_guess: Mapped[str | None] = mapped_column(String(24))
    user_confidence: Mapped[int | None] = mapped_column(Integer)
    red_flags: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    data_origin: Mapped[str] = mapped_column(String(9))


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(
            "data_origin IN ('real', 'synthetic')", name="ck_claims_origin"
        ),
        CheckConstraint("direction IN ('up', 'down')", name="ck_claims_direction"),
        CheckConstraint("window_days BETWEEN 1 AND 252", name="ck_claims_window_days"),
        CheckConstraint(
            "status IN ('open', 'scored', 'needs_review', 'unscorable')",
            name="ck_claims_status",
        ),
        Index("ix_claims_status_id", "status", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("submissions.id"))
    tip_quality: Mapped[dict[str, object] | None] = mapped_column(JSON)
    tip_quality_version: Mapped[str | None] = mapped_column(String(64))
    rating_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    symbol: Mapped[str | None] = mapped_column(String(32))
    direction: Mapped[str | None] = mapped_column(String(4))
    entry: Mapped[float | None] = mapped_column(Float)
    target: Mapped[float | None] = mapped_column(Float)
    stop: Mapped[float | None] = mapped_column(Float)
    window_days: Mapped[int] = mapped_column(Integer)
    window_end: Mapped[date | None] = mapped_column(Date)
    scorable: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(12))
    outcome: Mapped[dict[str, object] | None] = mapped_column(JSON)
    data_origin: Mapped[str] = mapped_column(String(9))


class SourceRatingHistory(Base):
    __tablename__ = "source_rating_history"
    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 0 AND 100", name="ck_source_rating_history_score"
        ),
        CheckConstraint(
            "data_origin IN ('real', 'synthetic')",
            name="ck_source_rating_history_origin",
        ),
        CheckConstraint(
            "label IN ('reliable', 'semi_reliable', 'not_reliable', 'not_enough_history')",
            name="ck_source_rating_history_label",
        ),
        Index("ix_source_rating_history_source_time", "source_id", "changed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id"))
    score: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(24))
    formula_version: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(String(9))


class SourceMention(Base):
    __tablename__ = "source_mentions"
    __table_args__ = (
        UniqueConstraint("source_id", "url", name="uq_source_mentions_url"),
        CheckConstraint(
            "data_origin IN ('real', 'synthetic')", name="ck_source_mentions_origin"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    platform: Mapped[str] = mapped_column(String(32))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(String(9))
