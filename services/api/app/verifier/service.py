"""Verifier use cases; the platform binds the core interfaces and DB session."""

from datetime import UTC
from hashlib import sha256
from uuid import UUID, uuid5

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.errors import ConfigurationError
from app.core.provenance import aggregate_data_origin

from .extraction import ExtractedClaim, extract_claim, reject_advice_request
from .ingestion import CapturedTip, ingest
from .models import Claim, Source, SourceRatingHistory, Submission
from .ports import MARKET_TZ, SessionFactory, VerifierCore
from .red_flags import collect_flags
from .repository import (
    save_submission,
    source_for,
    source_view,
    submission_for,
    update_rating,
)
from .schemas import (
    ClaimOutcome,
    ClaimStatus,
    ClaimView,
    DataOrigin,
    Mode,
    RatingChange,
    RedFlag,
    RedFlagCode,
    SourceLabel,
    SourceResponse,
    SourceView,
    SubmissionItem,
    SubmissionsResponse,
    VerifyRequest,
    VerifyResponse,
)


class SourceNotFound(LookupError):
    pass


class VerifierService:
    def __init__(self, sessions: SessionFactory, core: VerifierCore):
        self.sessions = sessions
        self.core = core

    def verify(self, owner: UUID, level: int, request: VerifyRequest) -> VerifyResponse:
        tip = ingest(
            text=request.text, url=request.url, image_base64=request.image_base64
        )
        digest = (
            sha256(f"{tip.post_url}\n{tip.content_hash}".encode()).hexdigest()
            if tip.post_url
            else tip.content_hash
        )
        reject_advice_request(tip.text)
        mode = Mode.FULL if level >= 3 else Mode.BASIC
        with self.sessions() as session, session.begin():
            pair = submission_for(session, owner, digest)
            if pair is not None:
                return self._verification(session, *pair, mode)
            if request.text is not None:
                demo = self._find_demo(session, tip)
                if demo is not None:
                    return self._copy_demo(session, owner, request, tip, *demo, mode)
        degraded = False
        try:
            claim = extract_claim(tip.text, self.core)
        except ConfigurationError:
            degraded = True
            mode = Mode.BASIC
            claim = ExtractedClaim(status=ClaimStatus.NEEDS_REVIEW)
        # Only stable, provider-verified authors may drive a shared real source rating.
        # A YouTube transcript can be unlisted or quote a guest; never rate the uploader from it.
        public = bool(
            tip.author_verified and tip.post_url and tip.handle and tip.published_at
        )
        if public and tip.handle:
            handle = tip.handle.casefold()
        else:
            handle = "private-" + uuid5(owner, f"{tip.platform}:{tip.handle or ''}").hex
        observed = (tip.published_at or tip.captured_at).astimezone(MARKET_TZ).date()
        registered = self.core.market.sebi_registered(handle) if public else None
        found = registered["found"] if registered is not None else None
        deleted = bool(
            public
            and tip.post_url
            and self.core.post_deleted is not None
            and self.core.post_deleted(tip.post_url) is True
        )
        market_symbol = (
            claim.symbol if tip.published_at is not None or not tip.post_url else None
        )
        flags = collect_flags(
            text=tip.text,
            symbol=market_symbol,
            applicable_date=observed,
            vague=claim.status == ClaimStatus.UNSCORABLE,
            registered=found,
            deleted=deleted,
            origin=DataOrigin.REAL,
            core=self.core,
        )
        with self.sessions() as session, session.begin():
            source = source_for(session, tip.platform, handle, DataOrigin.REAL)
            if registered is not None:
                source.sebi_registered = found
                source.sebi_reg_no = registered["reg_no"] if found else None
            prior = None
            if tip.post_url:
                prior = session.scalar(
                    select(Submission.content_hash)
                    .where(
                        Submission.source_id == source.id,
                        Submission.post_url == tip.post_url,
                    )
                    .order_by(Submission.captured_at, Submission.id)
                    .limit(1)
                )
            changed_revision = prior is not None and prior != digest
            status = ClaimStatus.NEEDS_REVIEW if changed_revision else claim.status
            submission, stored = save_submission(
                session,
                Submission(
                    user_id=owner,
                    source_id=source.id,
                    raw_content=tip.text,
                    content_hash=digest,
                    captured_at=tip.captured_at,
                    published_at=tip.published_at,
                    post_url=tip.post_url,
                    deleted_at=tip.captured_at if deleted else None,
                    user_guess=request.user_guess,
                    user_confidence=request.user_confidence,
                    red_flags=[flag.model_dump(mode="json") for flag in flags],
                    data_origin=DataOrigin.REAL,
                ),
                Claim(
                    symbol=claim.symbol,
                    direction=claim.direction,
                    entry=claim.entry,
                    target=claim.target,
                    stop=claim.stop,
                    window_days=claim.window_days,
                    scorable=status == ClaimStatus.OPEN,
                    status=status,
                    data_origin=DataOrigin.REAL,
                    rating_eligible=public and prior is None and not degraded,
                ),
            )
            if public and not degraded:
                update_rating(session, source)
            return self._verification(session, submission, stored, mode)

    def source(self, owner: UUID, source_id: UUID) -> SourceResponse:
        with self.sessions() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise SourceNotFound
            query = (
                select(Claim)
                .join(Submission, Submission.id == Claim.submission_id)
                .where(
                    Submission.source_id == source_id,
                )
            )
            if source.handle.startswith("private-"):
                owned = Submission.source_id == source_id, Submission.user_id == owner
                if not session.scalar(select(exists().where(*owned))):
                    raise SourceNotFound
                query = query.where(Submission.user_id == owner)
            else:
                query = query.where(
                    Claim.rating_eligible.is_(True), Submission.deleted_at.is_(None)
                )
            recent = session.scalars(
                query.order_by(Submission.captured_at.desc(), Claim.id).limit(20)
            )
            history = session.scalars(
                select(SourceRatingHistory)
                .where(
                    SourceRatingHistory.source_id == source_id,
                    SourceRatingHistory.label != "not_enough_history",
                )
                .order_by(SourceRatingHistory.changed_at, SourceRatingHistory.id)
            )
            return SourceResponse(
                source=self._source_view(session, source),
                history=[
                    RatingChange(
                        score=row.score,
                        label=SourceLabel(row.label),
                        reason=self.safe_text(row.reason),
                        changed_at=row.changed_at,
                        data_origin=DataOrigin(row.data_origin),
                    )
                    for row in history
                ],
                recent_claims=[ClaimView.model_validate(row) for row in recent],
                data_origin=DataOrigin(source.data_origin),
            )

    def submissions(self, owner: UUID, level: int) -> SubmissionsResponse:
        with self.sessions() as session:
            rows = session.execute(
                select(Submission, Claim)
                .join(
                    Claim,
                    Claim.submission_id == Submission.id,
                )
                .where(Submission.user_id == owner)
                .order_by(Submission.captured_at.desc(), Submission.id)
            )
            items = [
                SubmissionItem(
                    submission_id=submission.id,
                    claim=ClaimView.model_validate(claim),
                    status=ClaimStatus(claim.status),
                    outcome=(
                        ClaimOutcome.model_validate(claim.outcome)
                        if level >= 3 and claim.outcome is not None
                        else None
                    ),
                    data_origin=DataOrigin(submission.data_origin),
                )
                for submission, claim in rows
            ]
            origin = aggregate_data_origin(
                [item.data_origin.value for item in items],
                empty_default="real",
            )
            return SubmissionsResponse(items=items, data_origin=origin)

    def safe_text(self, text: str) -> str:
        return self.core.check_output(text).text

    def _source_view(
        self, session: Session, source: Source, *, basic: bool = False
    ) -> SourceView:
        view = source_view(session, source, basic=basic)
        view.handle = self.safe_text(view.handle)
        if view.facts is not None and view.facts.sebi_reg_no is not None:
            view.facts.sebi_reg_no = self.safe_text(view.facts.sebi_reg_no)
        return view

    def _verification(
        self, session: Session, submission: Submission, claim: Claim, mode: Mode
    ) -> VerifyResponse:
        source = session.get_one(Source, submission.source_id)
        flags = [RedFlag.model_validate(raw) for raw in submission.red_flags]
        if submission.deleted_at is not None and not any(
            flag.code == RedFlagCode.DELETED_POST for flag in flags
        ):
            flags.append(
                RedFlag(
                    code=RedFlagCode.DELETED_POST,
                    text="The original post was confirmed deleted.",
                    evidence={"deleted": True},
                    data_origin=DataOrigin(submission.data_origin),
                )
            )
        for flag in flags:
            if (
                flag.code == RedFlagCode.DELETED_POST
                and submission.post_url
                and self.core.deletion_provenance
            ):
                flag.evidence.update(self.core.deletion_provenance(submission.post_url))
            flag.text = self.safe_text(flag.text)
            flag.evidence = {
                key: self.safe_text(value) if isinstance(value, str) else value
                for key, value in flag.evidence.items()
            }
        return VerifyResponse(
            submission_id=submission.id,
            source=self._source_view(session, source, basic=mode == Mode.BASIC),
            claim=ClaimView.model_validate(claim),
            red_flags=flags,
            mode=mode,
            data_origin=DataOrigin(submission.data_origin),
        )

    def _find_demo(
        self, session: Session, tip: CapturedTip
    ) -> tuple[Submission, Claim] | None:
        pair = session.execute(
            select(Submission, Claim)
            .join(Claim, Claim.submission_id == Submission.id)
            .join(Source, Source.id == Submission.source_id)
            .where(
                Claim.rating_eligible.is_(True),
                Source.handle == "demo-forward-desk",
                Source.data_origin == DataOrigin.SYNTHETIC,
                Submission.data_origin == DataOrigin.SYNTHETIC,
                Submission.content_hash == tip.content_hash,
            )
            .order_by(Submission.captured_at, Submission.id)
            .limit(1)
        ).first()
        return (pair[0], pair[1]) if pair is not None else None

    def _copy_demo(
        self,
        session: Session,
        owner: UUID,
        request: VerifyRequest,
        tip: CapturedTip,
        exemplar: Submission,
        claim: Claim,
        mode: Mode,
    ) -> VerifyResponse:
        submission, stored = save_submission(
            session,
            Submission(
                user_id=owner,
                source_id=exemplar.source_id,
                raw_content=tip.text,
                content_hash=tip.content_hash,
                captured_at=tip.captured_at.astimezone(UTC),
                published_at=exemplar.published_at,
                user_guess=request.user_guess,
                user_confidence=request.user_confidence,
                red_flags=exemplar.red_flags,
                data_origin=DataOrigin.SYNTHETIC,
            ),
            Claim(
                symbol=claim.symbol,
                direction=claim.direction,
                entry=claim.entry,
                target=claim.target,
                stop=claim.stop,
                window_days=claim.window_days,
                window_end=claim.window_end,
                status=claim.status,
                scorable=claim.scorable,
                outcome=claim.outcome,
                data_origin=DataOrigin.SYNTHETIC,
            ),
        )
        return self._verification(session, submission, stored, mode)
