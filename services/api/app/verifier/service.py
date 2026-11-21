"""Verifier use cases; the platform binds the core interfaces and DB session."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4, uuid5

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConfigurationError
from app.core.provenance import aggregate_data_origin

from .extraction import (
    ExtractedClaim,
    extract_claim,
    extract_video_claims,
    reject_advice_request,
)
from .ingestion import CapturedTip, ingest
from .models import Claim, Source, SourceMention, Submission
from .ports import MARKET_TZ, SessionFactory, VerifierCore
from .provider_profile import (
    MentionResult,
    apply_enforcement,
    apply_mentions,
    fetch_mentions,
    needs_mention_refresh,
    refresh,
)
from .red_flags import collect_flags
from .repository import (
    rating_history,
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
    EnforcementView,
    MentionView,
    Mode,
    RatingChange,
    RedFlag,
    RedFlagCode,
    SourceLabel,
    SourceResponse,
    SourceView,
    SubmissionItem,
    SubmissionsResponse,
    TipFact,
    VerifyRequest,
    VerifyResponse,
)
from .tip_quality import VERSION, compute, facts

# Only submitters at or above this level may move a third-party public source's rating.
RATING_MIN_SUBMITTER_LEVEL = 3


def _claim_order(claim: Claim) -> int:
    raw = (claim.tip_quality or {}).get("claim_order", 0)
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else 0


class SourceNotFound(LookupError):
    pass


class VerifierService:
    def __init__(self, sessions: SessionFactory, core: VerifierCore):
        self.sessions = sessions
        self.core = core

    def verify(self, owner: UUID, level: int, request: VerifyRequest) -> VerifyResponse:
        if self.core.transcribe is None:
            tip = ingest(
                text=request.text, url=request.url, image_base64=request.image_base64
            )
        else:
            tip = ingest(
                text=request.text,
                url=request.url,
                image_base64=request.image_base64,
                transcribe=self.core.transcribe,
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
            extracted = (
                extract_video_claims(tip.transcript_segments, self.core)
                if tip.transcript_segments
                else [extract_claim(tip.text, self.core)]
            )
        except ConfigurationError:
            degraded = True
            mode = Mode.BASIC
            extracted = [ExtractedClaim(status=ClaimStatus.NEEDS_REVIEW)]
        claim = extracted[0]
        published = (
            tip.published_at.astimezone(MARKET_TZ).date() if tip.published_at else None
        )
        qualities = []
        for order, item in enumerate(extracted):
            quality = compute(
                symbol=item.symbol,
                direction=item.direction,
                target=item.target,
                stop=item.stop,
                window=item.window_days,
                posted=published,
                core=self.core,
                origin=DataOrigin.REAL,
            )
            quality.update(
                claim_order=order,
                evidence_start_s=item.evidence_start_s,
                evidence_end_s=item.evidence_end_s,
            )
            qualities.append(quality)
        # Only stable, provider-verified authors may drive a shared real source rating.
        # Preserve existing eligibility: a transcript alone cannot establish authorship.
        public = bool(
            tip.author_verified and tip.post_url and tip.handle and tip.published_at
        )
        # Low-level accounts can still verify tips, but their claims never count toward a
        # shared public source's rating (anti-poisoning). Private sources are unaffected.
        counts_toward_rating = public and level >= RATING_MIN_SUBMITTER_LEVEL
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
        # Network I/O happens here, before the source row lock is taken below.
        mentions = (
            self._fetch_mentions_unlocked(tip.platform, handle)
            if public and not degraded
            else None
        )
        with self.sessions() as session, session.begin():
            source = source_for(session, tip.platform, handle, DataOrigin.REAL)
            existing = submission_for(session, owner, digest)
            if existing is not None:
                return self._verification(session, *existing, mode)
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
            proposed_id = uuid4()
            submission, stored = save_submission(
                session,
                Submission(
                    id=proposed_id,
                    user_id=owner,
                    source_id=source.id,
                    raw_content=tip.text,
                    transcript_segments=tip.transcript_segments,
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
                    tip_quality=qualities[0],
                    tip_quality_version=VERSION,
                    symbol=claim.symbol,
                    direction=claim.direction,
                    entry=claim.entry,
                    target=claim.target,
                    stop=claim.stop,
                    window_days=claim.window_days,
                    scorable=status == ClaimStatus.OPEN,
                    status=status,
                    data_origin=DataOrigin.REAL,
                    rating_eligible=counts_toward_rating
                    and prior is None
                    and not degraded,
                ),
            )
            if submission.id != proposed_id:
                return self._verification(session, submission, stored, mode)
            # The source row lock serializes first-sighting ownership across writers.
            for item, quality in zip(extracted[1:], qualities[1:], strict=True):
                extra_status = (
                    ClaimStatus.NEEDS_REVIEW if changed_revision else item.status
                )
                session.add(
                    Claim(
                        submission_id=submission.id,
                        symbol=item.symbol,
                        direction=item.direction,
                        entry=item.entry,
                        target=item.target,
                        stop=item.stop,
                        window_days=item.window_days,
                        scorable=extra_status == ClaimStatus.OPEN,
                        status=extra_status,
                        data_origin=DataOrigin.REAL,
                        rating_eligible=counts_toward_rating
                        and prior is None
                        and not degraded,
                        tip_quality=quality,
                        tip_quality_version=VERSION,
                    )
                )
            session.flush()
            if public and not degraded:
                if not handle.startswith("private-"):
                    apply_enforcement(source)
                    apply_mentions(session, source, mentions or [])
                if counts_toward_rating:
                    update_rating(session, source)
            return self._verification(session, submission, stored, mode)

    def source(self, owner: UUID, source_id: UUID) -> SourceResponse:
        with self.sessions() as session, session.begin():
            # No row lock is taken, and the rating is never recomputed here: ratings are
            # written by verify() and the scheduled jobs. Mentions are refreshed lazily,
            # only when stored ones are older than 24 hours.
            source = session.scalar(select(Source).where(Source.id == source_id))
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
            if (
                self.core.web_search is not None
                and not source.handle.startswith("private-")
                and self._mentions_stale(session, source)
            ):
                refresh(session, source, self.core)
            recent = session.scalars(
                query.order_by(Submission.captured_at.desc(), Claim.id).limit(20)
            )
            history = rating_history(session, source_id)
            return SourceResponse(
                source=self._source_view(session, source),
                history=[
                    RatingChange(
                        score=row.score,
                        label=SourceLabel(row.label),
                        reason=self.safe_text(row.reason),
                        changed_at=row.changed_at,
                        formula_version=row.formula_version,
                        data_origin=DataOrigin(row.data_origin),
                    )
                    for row in history
                ],
                recent_claims=[self._claim_view(row) for row in recent],
                enforcement=EnforcementView(
                    flag=source.enforcement_flag,
                    refs=[
                        {key: self.safe_text(str(value)) for key, value in ref.items()}
                        for ref in (source.enforcement_refs or [])
                    ],
                    data_origin=DataOrigin(source.data_origin),
                ),
                mentions=[
                    MentionView.model_validate(row).model_copy(
                        update={"title": self.safe_text(row.title)}
                    )
                    for row in session.scalars(
                        select(SourceMention)
                        .where(SourceMention.source_id == source.id)
                        .order_by(SourceMention.fetched_at.desc(), SourceMention.id)
                        .limit(20)
                    )
                ],
                data_origin=DataOrigin(source.data_origin),
            )

    def _fetch_mentions_unlocked(
        self, platform: str, handle: str
    ) -> list[MentionResult] | None:
        """Staleness check (read-only session), then network fetch with no transaction open.

        Returns None when no refresh is due. The caller stores the result under the lock.
        """
        if handle.startswith("private-"):
            return None
        with self.sessions() as session:
            source = session.scalar(
                select(Source).where(
                    Source.platform == platform,
                    Source.handle == handle,
                    Source.data_origin == DataOrigin.REAL,
                )
            )
            # A source not yet created has no mentions; a transient row with no id
            # reads as "never fetched" in `needs_mention_refresh`.
            probe = source or Source(
                platform=platform, handle=handle, data_origin=DataOrigin.REAL
            )
            if not needs_mention_refresh(session, probe, self.core):
                return None
        return fetch_mentions(
            handle=handle, platform=platform, origin=DataOrigin.REAL, core=self.core
        )

    @staticmethod
    def _mentions_stale(session: Session, source: Source) -> bool:
        latest = session.scalar(
            select(func.max(SourceMention.fetched_at)).where(
                SourceMention.source_id == source.id
            )
        )
        if latest is None:
            return True
        latest = latest.replace(tzinfo=UTC) if latest.tzinfo is None else latest
        return datetime.now(UTC) - latest >= timedelta(hours=24)

    def submissions(
        self, owner: UUID, level: int, *, limit: int = 50, offset: int = 0
    ) -> SubmissionsResponse:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        with self.sessions() as session:
            rows = session.execute(
                select(Submission, Claim)
                .join(
                    Claim,
                    Claim.submission_id == Submission.id,
                )
                .where(Submission.user_id == owner)
                .order_by(Submission.captured_at.desc(), Submission.id, Claim.id)
                .limit(limit + 1)
                .offset(offset)
            ).all()
            has_more = len(rows) > limit
            rows = rows[:limit]
            items = [
                SubmissionItem(
                    submission_id=submission.id,
                    claim=self._claim_view(claim),
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
            return SubmissionsResponse(
                items=items,
                data_origin=origin,
                next_offset=offset + limit if has_more else None,
            )

    def _claim_view(self, claim: Claim) -> ClaimView:
        view = ClaimView.model_validate(claim)
        view.tip_facts = [
            TipFact.model_validate(row) for row in facts(claim.tip_quality, self.core)
        ]
        if claim.tip_quality:
            view.evidence_start_s = (
                float(v)
                if isinstance(
                    (v := claim.tip_quality.get("evidence_start_s")), (float, int)
                )
                else None
            )
            view.evidence_end_s = (
                float(v)
                if isinstance(
                    (v := claim.tip_quality.get("evidence_end_s")), (float, int)
                )
                else None
            )
        return view

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
        retained = list(
            session.scalars(select(Claim).where(Claim.submission_id == submission.id))
        )
        retained.sort(key=lambda c: (_claim_order(c), c.id))
        views = [self._claim_view(c) for c in retained]
        return VerifyResponse(
            submission_id=submission.id,
            source=self._source_view(session, source, basic=mode == Mode.BASIC),
            claim=views[0],
            claims=views,
            tip_facts=views[0].tip_facts,
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
