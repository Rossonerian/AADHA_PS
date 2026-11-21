"""Transactional data access for submissions and public-source ratings."""

from datetime import UTC, datetime, timedelta
from statistics import mean
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings

from .models import Claim, Source, SourceRatingHistory, Submission
from .schemas import DataOrigin, SourceFacts, SourceLabel, SourceView
from .scoring import rate_source


def source_for(
    session: Session, platform: str, handle: str, origin: DataOrigin
) -> Source:
    query = select(Source).where(
        Source.platform == platform,
        Source.handle == handle,
        Source.data_origin == origin,
    )
    existing = session.scalar(query.with_for_update())
    if existing is not None:
        return existing
    source = Source(platform=platform, handle=handle, data_origin=origin)
    try:
        with session.begin_nested():
            session.add(source)
            session.flush()
    except IntegrityError:
        existing = session.scalar(query.with_for_update())
        if existing is None:
            raise
        return existing
    return source


def submission_for(
    session: Session, owner: UUID, digest: str
) -> tuple[Submission, Claim] | None:
    pair = session.execute(
        select(Submission, Claim)
        .join(Claim, Claim.submission_id == Submission.id)
        .where(
            Submission.user_id == owner,
            Submission.content_hash == digest,
        )
        .order_by(Claim.id)
    ).first()
    return (pair[0], pair[1]) if pair is not None else None


def save_submission(
    session: Session, submission: Submission, claim: Claim
) -> tuple[Submission, Claim]:
    try:
        with session.begin_nested():
            session.add(submission)
            session.flush()
            claim.submission_id = submission.id
            session.add(claim)
            session.flush()
    except IntegrityError:
        pair = submission_for(session, submission.user_id, submission.content_hash)
        if pair is None:
            raise
        return pair
    return submission, claim


def rating_evidence(session: Session, source: Source) -> tuple[SourceFacts, int, int]:
    rows = session.execute(
        select(Submission, Claim)
        .join(Claim, Claim.submission_id == Submission.id)
        .where(
            Submission.source_id == source.id,
            Submission.data_origin == source.data_origin,
        )
        .order_by(Submission.captured_at, Submission.id)
    )
    seen: dict[str, tuple[bool, bool, bool | None]] = {}
    for submission, claim in rows:
        if not claim.rating_eligible or claim.data_origin != source.data_origin:
            continue
        key = str(
            (
                submission.post_url or submission.content_hash,
                claim.symbol,
                claim.direction,
                claim.entry,
                claim.target,
                claim.stop,
                claim.window_days,
            )
        )
        deleted, flagged, correct = seen.get(key, (False, False, None))
        outcome = claim.outcome if claim.status == "scored" else None
        observed = outcome.get("correct") if outcome is not None else None
        seen[key] = (
            deleted or submission.deleted_at is not None,
            flagged or bool(submission.red_flags),
            (
                correct
                if correct is not None
                else observed if isinstance(observed, bool) else None
            ),
        )
    facts = SourceFacts(
        calls_tracked=len(seen),
        correct=sum(correct is True for _, _, correct in seen.values()),
        deleted=sum(deleted for deleted, _, _ in seen.values()),
        sebi_registered=source.sebi_registered,
        sebi_reg_no=source.sebi_reg_no,
    )
    return (
        facts,
        sum(correct is not None for _, _, correct in seen.values()),
        sum(flagged or deleted for deleted, flagged, _ in seen.values()),
    )


def update_rating(session: Session, source: Source) -> None:
    facts, scored, flagged = rating_evidence(session, source)
    weight = get_settings().tip_quality_weight
    qualities = [
        c.tip_quality.get("tip_quality_score")
        for c in session.scalars(
            select(Claim)
            .join(Submission)
            .where(
                Submission.source_id == source.id,
                Claim.rating_eligible.is_(True),
                Claim.status == "scored",
                Claim.data_origin == source.data_origin,
            )
        )
        if c.tip_quality
    ]
    quality_values = [
        float(q) for q in qualities if isinstance(q, (int, float)) and 0 <= q <= 1
    ]
    score, label = rate_source(
        scored=scored,
        correct=facts.correct,
        tracked=facts.calls_tracked,
        deleted=facts.deleted,
        registered=facts.sebi_registered,
        flagged=flagged,
        enforcement=source.enforcement_flag,
        tip_quality=mean(quality_values) if quality_values else None,
        tip_quality_weight=weight,
    )
    source.scored_claims = scored
    last = session.execute(
        select(
            SourceRatingHistory.score,
            SourceRatingHistory.label,
            SourceRatingHistory.changed_at,
        )
        .where(SourceRatingHistory.source_id == source.id)
        .order_by(SourceRatingHistory.changed_at.desc(), SourceRatingHistory.id.desc())
        .limit(1)
    ).first()
    changed = (
        last is None
        or last.score != score
        or last.label != label
        or source.score != score
        or source.label != label
    )
    source.score, source.label = score, label
    if not changed:
        return
    # All writers hold the source lock. Ensure ordering on clocks with coarse resolution.
    changed_at = datetime.now(UTC)
    if last is not None:
        prev = last.changed_at
        prev = prev.replace(tzinfo=UTC) if prev.tzinfo is None else prev
        changed_at = max(changed_at, prev + timedelta(microseconds=1))
    session.add(
        SourceRatingHistory(
            source_id=source.id,
            score=score,
            label=label,
            reason="Updated from tracked claims and source evidence.",
            formula_version=f"source-v2-q{weight}",
            changed_at=changed_at,
            data_origin=source.data_origin,
        )
    )


HISTORY_LIMIT = 50


def rating_history(
    session: Session, source_id: UUID, limit: int = HISTORY_LIMIT
) -> list[SourceRatingHistory]:
    """Latest `limit` meaningful rating changes, returned oldest first."""
    rows = session.scalars(
        select(SourceRatingHistory)
        .where(
            SourceRatingHistory.source_id == source_id,
            SourceRatingHistory.label != "not_enough_history",
        )
        .order_by(SourceRatingHistory.changed_at.desc(), SourceRatingHistory.id.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


def source_view(session: Session, source: Source, *, basic: bool = False) -> SourceView:
    facts = None if basic else rating_evidence(session, source)[0]
    label = SourceLabel(source.label)
    return SourceView(
        id=source.id,
        platform=source.platform,
        handle=(
            "unattributed" if source.handle.startswith("private-") else source.handle
        ),
        label=None if basic else label,
        score=(
            None if basic or label == SourceLabel.NOT_ENOUGH_HISTORY else source.score
        ),
        facts=facts,
        data_origin=DataOrigin(source.data_origin),
    )
