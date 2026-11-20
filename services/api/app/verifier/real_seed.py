"""Validate and load provenance-backed historical source claims, without an LLM."""

import json
from collections import Counter
from datetime import UTC, date, datetime, time
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import pandas as pd
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.models import UserRecord
from app.verifier.ingestion import redact_phone_numbers
from app.verifier.models import Claim, Source, Submission
from app.verifier.ports import MARKET_TZ
from app.verifier.repository import save_submission, source_for, update_rating
from app.verifier.schemas import ClaimOutcome, DataOrigin, Direction
from app.verifier.scoring import ScoringResult, evaluate_claim

SEED_OWNER = uuid5(NAMESPACE_URL, "paisaproof:public-research-importer:v1")


class PublicClaimSeed(BaseModel):
    publisher: str = Field(min_length=2, max_length=200)
    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9&.-]{0,31}$")
    company_name: str
    url: HttpUrl
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_date: date
    claim_page: int = Field(ge=1)
    direction: Direction
    target: float = Field(gt=0, allow_inf_nan=False)
    quoted_cmp: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    quoted_reference_range: list[float] | None = None
    cmp_evidence: str | None = None
    target_evidence: str
    horizon_evidence: str | None = None
    window_days: int = Field(ge=1, le=252)
    horizon_basis: Literal["stated_horizon", "verifier_default_20_sessions"]
    data_origin: Literal["real"]
    price_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    benchmark_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _prices(path: Path, digest: str) -> pd.DataFrame:
    if sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Price evidence digest mismatch: {path.name}")
    frame = pd.read_csv(
        path,
        converters={
            key: float for key in ("open", "high", "low", "close", "adj close")
        },
    )
    required = {"date", "close", "data_origin", "source"}
    if not required.issubset(frame.columns) or frame.empty:
        raise ValueError("Missing price evidence columns or rows")
    if not frame.data_origin.eq("real").all():
        raise ValueError("Real claims require exclusively real price evidence")
    if frame.date.duplicated().any():
        raise ValueError("Ambiguous duplicate price sessions")
    return frame


def validate_bundle(
    directory: Path, *, min_sources: int = 30
) -> list[tuple[PublicClaimSeed, ScoringResult]]:
    records = json.loads((directory / "claims.json").read_text(encoding="utf-8"))
    claims = [PublicClaimSeed.model_validate(row) for row in records]
    cohort = json.loads((directory / "cohort.json").read_text(encoding="utf-8"))[
        "publications"
    ]
    expected = {(r["publisher"], r["url"], r["sha256"]) for r in cohort}
    actual = {(c.publisher, str(c.url), c.sha256) for c in claims}
    if actual != expected or len(cohort) != len(claims):
        raise ValueError(
            "Frozen publication membership differs; do not reselect after outcomes"
        )
    if len({c.sha256 for c in claims}) != len(claims):
        raise ValueError("A physical report may contribute only one seed claim")
    if len({(c.publisher, c.symbol, c.report_date) for c in claims}) != len(claims):
        raise ValueError("Duplicate publisher/security/date claim")
    counts = Counter(c.publisher for c in claims)
    if len(counts) < min_sources or any(n < 5 for n in counts.values()):
        raise ValueError(
            "Real-source quota requires >=30 publishers with >=5 claims each"
        )
    results = []
    for claim in claims:
        if claim.url.scheme != "https":
            raise ValueError("Public report provenance must use HTTPS")
        if (
            claim.horizon_basis == "verifier_default_20_sessions"
            and claim.window_days != 20
        ):
            raise ValueError(
                "Unstated source horizons must retain the existing default"
            )
        stock = _prices(
            directory / "prices" / f"{claim.symbol}.csv", claim.price_sha256
        )
        benchmark = _prices(directory / "prices/NIFTY50.csv", claim.benchmark_sha256)
        stock = stock.loc[pd.to_datetime(stock.date).dt.date <= date(2026, 11, 20)]
        benchmark = benchmark.loc[
            pd.to_datetime(benchmark.date).dt.date <= date(2026, 11, 20)
        ]
        result = evaluate_claim(
            direction=claim.direction,
            start=claim.report_date,
            window_days=claim.window_days,
            stock=stock,
            benchmark=benchmark,
            target=claim.target,
        )
        if result is None or result.correct is None:
            raise ValueError(
                f"Missing complete, unambiguous price window: {claim.publisher}/{claim.symbol}"
            )
        results.append((claim, result))
    return results


def load_bundle(sessions: sessionmaker[Session], directory: Path) -> dict[str, Any]:
    """Preflight the entire quota before one atomic, idempotent database transaction."""
    validated = validate_bundle(directory)
    source_ids: set[UUID] = set()
    with sessions.begin() as db:
        owner = db.get(UserRecord, str(SEED_OWNER))
        if owner is None:
            db.add(
                UserRecord(
                    id=str(SEED_OWNER),
                    name="Public research archive importer",
                    current_level=1,
                )
            )
            db.flush()
        elif owner.name != "Public research archive importer":
            raise ValueError("Reserved import owner conflicts with an existing user")
        existing = {}
        for submission, claim in db.execute(
            select(Submission, Claim)
            .join(Claim, Claim.submission_id == Submission.id)
            .where(Submission.user_id == SEED_OWNER)
            .with_for_update()
        ):
            if submission.post_url in existing:
                raise ValueError("Duplicate public report under the import owner")
            existing[submission.post_url] = (submission, claim)
        publishers: dict[str, Source] = {}
        for record, score in validated:
            source = publishers.get(record.publisher)
            if source is None:
                source = source_for(
                    db, "broker_research", record.publisher, DataOrigin.REAL
                )
                publishers[record.publisher] = source
            source_ids.add(source.id)
            text = redact_phone_numbers(
                f"Historical source: {record.publisher}; report date {record.report_date}. "
                f"{record.company_name}. Quoted target field: {record.target_evidence}. "
                f"Scoring horizon basis: {record.horizon_basis}; {record.window_days} sessions."
                f" Document SHA256: {record.sha256}; claim page: {record.claim_page}."
                f" Adjusted price SHA256: {record.price_sha256};"
                f" benchmark SHA256: {record.benchmark_sha256}."
            )
            digest = sha256((str(record.url) + "\n" + text).encode()).hexdigest()
            outcome = ClaimOutcome(
                correct=bool(score.correct),
                method=score.method,
                stock_pct=score.stock_pct,
                index_pct=score.index_pct,
                data_origin=DataOrigin.REAL,
            )
            claim_values = dict(
                symbol=record.symbol,
                direction=record.direction,
                entry=None,
                target=record.target,
                stop=None,
                window_days=record.window_days,
                window_end=score.window_end,
                scorable=True,
                status="scored",
                outcome=outcome.model_dump(mode="json", exclude_none=True),
                rating_eligible=True,
                data_origin=DataOrigin.REAL,
            )
            pair = existing.get(str(record.url))
            if pair is not None:
                submission, claim = pair
                if (
                    submission.data_origin != "real"
                    or claim.data_origin != "real"
                    or submission.source_id != source.id
                ):
                    raise ValueError(
                        "Existing report origin or publisher differs; never relabel"
                    )
                submission.raw_content, submission.content_hash = text, digest
                submission.published_at = datetime.combine(
                    record.report_date, time.max, MARKET_TZ
                )
                for field, value in claim_values.items():
                    setattr(claim, field, value)
                continue
            save_submission(
                db,
                Submission(
                    id=uuid5(SEED_OWNER, digest),
                    user_id=SEED_OWNER,
                    source_id=source.id,
                    raw_content=text,
                    content_hash=digest,
                    captured_at=datetime.now(UTC),
                    published_at=datetime.combine(
                        record.report_date, time.max, MARKET_TZ
                    ),
                    post_url=str(record.url),
                    red_flags=[],
                    data_origin=DataOrigin.REAL,
                ),
                Claim(**claim_values),
            )
        db.flush()
        for sid in sorted(source_ids):
            locked_source = db.scalar(
                select(Source).where(Source.id == sid).with_for_update()
            )
            if locked_source is None:
                raise ValueError("Imported source disappeared")
            update_rating(db, locked_source)
    return {
        "status": "loaded",
        "data_origin": "real",
        "sources": len(source_ids),
        "claims": len(validated),
        "min_scored_claims": min(Counter(c.publisher for c, _ in validated).values()),
    }
