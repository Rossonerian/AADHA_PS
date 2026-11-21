"""Daily evaluation of open claims and refresh of confirmed deletion evidence."""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any, overload

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from .models import Claim, Source, Submission
from .ports import MARKET_TZ, SessionFactory, VerifierCore, platform_core
from .repository import update_rating
from .schemas import ClaimOutcome, ClaimStatus, DataOrigin, Direction
from .scoring import evaluate_claim

_logger = logging.getLogger("paisaproof.verifier.jobs")


def _levels_match_bars(row: Any, stock: Any) -> bool:
    """Guard the nominal-vs-adjusted assumption using the bars themselves.

    Platform bars are split/dividend adjusted. If the quoted levels are far from the
    first bar's close (e.g. after a split), they are not on the same basis.
    """
    try:
        first = float(stock["close"].iloc[0])
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if not first > 0:
        return False
    if row.entry is not None:
        return bool(0.9 <= row.entry / first <= 1.1)
    levels = [v for v in (row.target, row.stop) if v is not None]
    return bool(levels) and all(0.5 <= v / first <= 1.5 for v in levels)


def _score_one(
    sessions: SessionFactory, core: VerifierCore, row: Any, end: date
) -> int:
    """Evaluate and persist one claim; returns 1 when scored."""
    if not row.symbol or not row.direction:
        return 0
    if row.post_url and row.published_at is None:
        return (
            0  # Do not score historical public posts from the date a user found them.
        )
    timestamp = row.published_at or row.captured_at
    if timestamp.tzinfo is None:  # SQLite test/dev driver stores UTC without an offset.
        timestamp = timestamp.replace(tzinfo=UTC)
    start = timestamp.astimezone(MARKET_TZ).date()
    if start >= end:
        return 0
    through = min(end, start + timedelta(days=row.window_days * 2 + 35))
    if (
        row.target is not None
        and row.stop is not None
        and (
            core.nominal_price_basis is None
            or not core.nominal_price_basis(row.symbol, start, through)
        )
    ):
        return 0
    stock = core.market.prices(row.symbol, start, through)
    if (
        row.target is not None
        and row.stop is not None
        and not _levels_match_bars(row, stock)
    ):
        return 0  # Quoted levels are not on the adjusted bars' price basis.
    benchmark = core.market.index("NIFTY50", start, through)
    result = evaluate_claim(
        direction=Direction(row.direction),
        start=start,
        window_days=row.window_days,
        stock=stock,
        benchmark=benchmark,
        entry=row.entry,
        target=row.target,
        stop=row.stop,
    )
    if result is None:
        return 0
    with sessions() as session, session.begin():
        claim = session.scalar(
            select(Claim)
            .where(Claim.id == row.id, Claim.status == ClaimStatus.OPEN)
            .with_for_update()
        )
        if claim is None:
            return 0
        claim.window_end = result.window_end
        if result.correct is None:
            claim.status = ClaimStatus.NEEDS_REVIEW
            claim.scorable = False
            return 0
        claim.status = ClaimStatus.SCORED
        claim.outcome = ClaimOutcome(
            correct=result.correct,
            method=result.method,
            stock_pct=result.stock_pct,
            index_pct=result.index_pct,
            data_origin=DataOrigin.REAL,
        ).model_dump(mode="json", exclude_none=True)
        submission = session.get_one(Submission, claim.submission_id)
        if claim.rating_eligible:
            source = session.scalar(
                select(Source)
                .where(Source.id == submission.source_id)
                .with_for_update()
            )
            if source is not None and not source.handle.startswith("private-"):
                update_rating(session, source)
        return 1


def _score_open_claims(
    sessions: SessionFactory,
    core: VerifierCore,
    *,
    as_of: date | None = None,
    failures: list[str] | None = None,
) -> int:
    """Score eligible rows once. Missing or ambiguous observations are not wrong calls."""
    now = datetime.now(UTC)
    today = as_of or now.astimezone(MARKET_TZ).date()
    # Daily bars must be from completed calendar dates, not an in-progress session.
    end = today - timedelta(days=1)
    with sessions() as session:
        pending = list(
            session.execute(
                select(
                    Claim.id,
                    Claim.symbol,
                    Claim.direction,
                    Claim.window_days,
                    Claim.entry,
                    Claim.target,
                    Claim.stop,
                    Submission.captured_at,
                    Submission.published_at,
                    Submission.post_url,
                )
                .join(Submission, Submission.id == Claim.submission_id)
                .where(
                    Claim.status == ClaimStatus.OPEN,
                    Claim.scorable.is_(True),
                    Claim.data_origin == DataOrigin.REAL,
                )
                .order_by(Claim.id)
            )
        )
    scored = 0
    for row in pending:
        try:
            scored += _score_one(sessions, core, row, end)
        except Exception as exc:  # noqa: BLE001 - isolate per-claim failures
            _logger.warning(
                "score_claim_failed",
                extra={"claim_id": str(row.id), "error": str(exc)[:300]},
            )
            if failures is not None:
                failures.append(f"{row.id}: {type(exc).__name__}")
    if core.post_deleted is not None:
        try:
            _refresh_deletions(sessions, core, now)
        except Exception as exc:  # noqa: BLE001 - scored claims are already committed
            _logger.warning("refresh_deletions_failed", extra={"error": str(exc)[:300]})
            if failures is not None:
                failures.append(f"deletions: {type(exc).__name__}")
    return scored


@overload
def score_open_claims(
    sessions: SessionFactory, core: VerifierCore, *, as_of: date | None = None
) -> int: ...


@overload
def score_open_claims(
    sessions: Session | None = None, core: None = None, *, as_of: date | None = None
) -> dict[str, Any]: ...


def score_open_claims(
    sessions: SessionFactory | Session | None = None,
    core: VerifierCore | None = None,
    *,
    as_of: date | None = None,
) -> int | dict[str, Any]:
    """Score open claims via explicit Verifier bindings or the platform daily job Session."""
    if core is not None and callable(sessions):
        return _score_open_claims(sessions, core, as_of=as_of)
    if sessions is None:
        return {"status": "skipped", "scored": 0}
    if isinstance(sessions, Session):
        bind = sessions.get_bind()
        tables = set(inspect(bind).get_table_names())
        if not {"claims", "submissions", "sources"}.issubset(tables):
            return {"status": "skipped", "scored": 0}
        factory = sessionmaker(bind=bind, autoflush=False, expire_on_commit=False)
        failures: list[str] = []
        scored = _score_open_claims(
            factory, platform_core(), as_of=as_of, failures=failures
        )
        if failures:
            return {
                "status": "degraded",
                "scored": scored,
                "failed": len(failures),
                "failures": failures[:20],
            }
        return {"status": "ok", "scored": scored}
    raise TypeError(
        "score_open_claims requires a SessionFactory + VerifierCore or a Session | None"
    )


def _refresh_deletions(
    sessions: SessionFactory, core: VerifierCore, now: datetime
) -> None:
    if core.post_deleted is None:
        return
    with sessions() as session:
        posts = list(
            session.scalars(
                select(Submission.post_url)
                .join(Claim, Claim.submission_id == Submission.id)
                .where(
                    Submission.post_url.is_not(None),
                    Submission.deleted_at.is_(None),
                    Submission.data_origin == DataOrigin.REAL,
                    Claim.rating_eligible.is_(True),
                )
                .distinct()
            )
        )
    for post in posts:
        try:
            if post is None or core.post_deleted(post) is not True:
                continue
        except Exception as exc:  # noqa: BLE001 - one bad lookup must not stop others
            _logger.warning("post_deleted_failed", extra={"error": str(exc)[:300]})
            continue
        with sessions() as session, session.begin():
            affected = session.scalars(
                select(Submission)
                .where(
                    Submission.post_url == post,
                    Submission.deleted_at.is_(None),
                    Submission.data_origin == DataOrigin.REAL,
                )
                .with_for_update()
            ).all()
            for submission in affected:
                submission.deleted_at = now
            for source_id in sorted({submission.source_id for submission in affected}):
                source = session.scalar(
                    select(Source).where(Source.id == source_id).with_for_update()
                )
                if source is not None and not source.handle.startswith("private-"):
                    update_rating(session, source)
