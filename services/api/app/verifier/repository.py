"""Transactional data access for submissions and public-source ratings."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    ).one_or_none()
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
        key = submission.post_url or submission.content_hash
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
    score, label = rate_source(
        scored=scored,
        correct=facts.correct,
        tracked=facts.calls_tracked,
        deleted=facts.deleted,
        registered=facts.sebi_registered,
        flagged=flagged,
    )
    changed = (source.score, source.label) != (score, label)
    source.scored_claims = scored
    source.score, source.label = score, label
    if changed:
        # All writers hold the source lock. Ensure ordering on clocks with coarse resolution.
        last = session.scalar(
            select(SourceRatingHistory.changed_at)
            .where(SourceRatingHistory.source_id == source.id)
            .order_by(SourceRatingHistory.changed_at.desc())
            .limit(1)
        )
        changed_at = datetime.now(UTC)
        if last is not None:
            last = last.replace(tzinfo=UTC) if last.tzinfo is None else last
            changed_at = max(changed_at, last + timedelta(microseconds=1))
        session.add(
            SourceRatingHistory(
                source_id=source.id,
                score=score,
                label=label,
                reason="Updated from tracked claims and source evidence.",
                changed_at=changed_at,
                data_origin=source.data_origin,
            )
        )


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
