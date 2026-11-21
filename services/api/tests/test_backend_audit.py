"""Regression tests for the backend audit fixes."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AppError
from app.education.enums import LessonStatus
from app.education.learning import build_or_update_plan, submit_lesson_check
from app.education.loader import load_seed_directory
from app.education.models import User as EduUser
from app.education.onboarding import _should_stop_onboarding
from app.education.repository import EducationRepository, apply_migrations
from app.nasdaq_verifier import service as nasdaq
from app.nasdaq_verifier.gate import GateInputs, missing_requirements
from app.verifier.extraction import extract_video_claims
from app.verifier.jobs import _score_open_claims
from app.verifier.models import (
    Base,
    Claim,
    Source,
    SourceRatingHistory,
    Submission,
)
from app.verifier.ports import VerifierCore, platform_core
from app.verifier.provider_profile import (
    apply_mentions,
    fetch_mentions,
    needs_mention_refresh,
)
from app.verifier.repository import rating_history, update_rating
from tests.test_verifier_v2_integration import core as v2_core
from tests.test_verifier_v2_integration import parsed

# ---- 1. rating history ------------------------------------------------------


@pytest.fixture
def vsessions(tmp_path: Any) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine)


def test_update_rating_records_history_only_when_rating_changes(vsessions):
    with vsessions.begin() as db:
        source = Source(platform="telegram", handle="desk", data_origin="real")
        db.add(source)
        db.flush()
        for _ in range(5):
            update_rating(db, source)
        count = db.scalar(select(func.count()).select_from(SourceRatingHistory))
        assert count == 1  # first computation only; identical recomputes are no-ops
        source.score = 77  # force a visible change on the next recompute
        db.add(
            SourceRatingHistory(
                source_id=source.id,
                score=77,
                label="reliable",
                reason="x",
                formula_version="v",
                changed_at=datetime.now(UTC),
                data_origin="real",
            )
        )
        db.flush()
        update_rating(db, source)
        count = db.scalar(select(func.count()).select_from(SourceRatingHistory))
        assert count == 3  # a changed rating appends exactly one row


def test_rating_history_read_is_capped_and_chronological(vsessions):
    with vsessions.begin() as db:
        source = Source(platform="telegram", handle="desk2", data_origin="real")
        db.add(source)
        db.flush()
        for i in range(80):
            db.add(
                SourceRatingHistory(
                    source_id=source.id,
                    score=i,
                    label="reliable",
                    reason="x",
                    formula_version="v",
                    changed_at=datetime(2025, 1, 1, tzinfo=UTC)
                    + pd.Timedelta(minutes=i),
                    data_origin="real",
                )
            )
        db.flush()
        rows = rating_history(db, source.id)
        assert len(rows) == 50
        assert [r.score for r in rows] == list(range(30, 80))


# ---- 2. provider profile: no HTTP in the DB phase ---------------------------


def test_fetch_mentions_needs_no_session_and_write_is_separate(vsessions):
    from app.core.guardrails import check_output
    from app.core.web_search import SearchResult

    calls: list[str] = []

    def search(query, *, limit):
        calls.append(query)
        return [SearchResult(url="https://example.org/a", title="Public discussion")]

    core = v2_core(search=search)
    mentions = fetch_mentions(
        handle="desk3", platform="telegram", origin="real", core=core
    )
    assert calls == ['"desk3" "telegram"'] and len(mentions) == 1
    with vsessions.begin() as db:
        source = Source(platform="telegram", handle="desk3", data_origin="real")
        db.add(source)
        db.flush()
        assert needs_mention_refresh(db, source, core)
        apply_mentions(db, source, mentions)
        db.flush()
        assert not needs_mention_refresh(db, source, core)
    assert check_output  # guard import used by the core fixture


def test_verify_fetches_mentions_before_taking_the_source_lock(tmp_path, monkeypatch):
    from app.verifier import service as verifier_service
    from app.verifier.ingestion import CapturedTip
    from app.verifier.models import SourceMention
    from app.verifier.provider_profile import MentionResult
    from app.verifier.schemas import VerifyRequest

    engine = create_engine(f"sqlite:///{tmp_path / 'lock_order.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    opened: list[Session] = []

    def tracked_session() -> Session:
        session = sessions()
        opened.append(session)
        return session

    now = datetime.now(UTC)
    text = "TCS will rise; target 120; stop 90."
    tip = CapturedTip(
        text=text,
        platform="telegram",
        handle="Lock-Order-Desk",
        content_hash="a" * 64,
        captured_at=now,
        published_at=now,
        post_url="https://t.me/lock_order/1",
        author_verified=True,
    )
    monkeypatch.setattr(verifier_service, "ingest", lambda **_: tip)
    calls: list[bool] = []

    def spy_fetch(**kwargs):
        # No session may hold an open transaction (and so a row lock) during HTTP.
        calls.append(any(s.in_transaction() for s in opened))
        return [MentionResult("https://example.org/mention", "Public", None)]

    monkeypatch.setattr(verifier_service, "fetch_mentions", spy_fetch)
    service = verifier_service.VerifierService(
        tracked_session, v2_core(search=lambda query, *, limit: [])
    )
    service.verify(uuid.uuid4(), 3, VerifyRequest(text=text))
    assert calls == [False]
    with sessions() as db:
        stored = db.scalars(select(SourceMention)).all()
        assert [m.url for m in stored] == ["https://example.org/mention"]
    engine.dispose()


# ---- 3. ensure_user race-safety --------------------------------------------


def test_ensure_user_sqlite_is_idempotent_under_conflict():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repo = EducationRepository(conn)
    uid = str(uuid.uuid4())
    first = repo.ensure_user(uid, name="First", level=2)
    second = repo.ensure_user(uid, name="Second", level=1)
    assert first["name"] == "First" and second["name"] == "First"
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_ensure_user_orm_recovers_from_integrity_error(db_session: Session):
    uid = str(uuid.uuid4())
    other = Session(bind=db_session.get_bind())
    other.add(EduUser(id=uid, name="Winner", current_level=3))
    other.commit()
    other.close()

    real_get = db_session.get
    seen = {"n": 0}

    def stale_get(entity, ident, *a, **k):
        seen["n"] += 1
        return None if seen["n"] == 1 else real_get(entity, ident, *a, **k)

    db_session.get = stale_get  # type: ignore[method-assign]
    out = EducationRepository(db_session).ensure_user(uid, name="Loser", level=1)
    assert out["name"] == "Winner" and out["current_level"] == 3


# ---- 4/5. onboarding + lessons ---------------------------------------------


@pytest.fixture
def edu() -> EducationRepository:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repo = EducationRepository(conn)
    load_seed_directory(repo)
    return repo


def _responses(skills: list[str], correct: bool) -> list[dict[str, Any]]:
    return [{"skill_area": s, "correct": correct} for s in skills]


def test_onboarding_stops_at_six_regardless_of_skill_balance():
    rotation = ["basics", "reading_stock", "judging_info", "risk"]
    assert _should_stop_onboarding(_responses(["basics"] * 5, True), 6) is False
    assert _should_stop_onboarding(_responses(["basics"] * 6, True), 6) is True
    assert _should_stop_onboarding(_responses(rotation + rotation[:2], True), 6) is True
    assert _should_stop_onboarding(_responses(rotation, True), 6) is False


def test_failed_retry_does_not_regress_completed_lesson(edu):
    edu.ensure_user("u1", level=1)
    plan = build_or_update_plan(edu, "u1", level=1)
    lesson_id = plan["lessons"][0]["id"]
    lesson = edu.get_lesson(lesson_id)
    good = [
        {"question_id": q["id"], "answer": q["answer"], "confidence": 80}
        for q in lesson["check_questions"]
    ]
    bad = [{**a, "answer": "definitely-wrong"} for a in good]
    assert submit_lesson_check(edu, "u1", lesson_id, good)["passed"] is True
    assert submit_lesson_check(edu, "u1", lesson_id, bad)["passed"] is False
    assert edu.get_plan("u1")["progress"][lesson_id] == LessonStatus.COMPLETED.value


def test_onboarding_retake_never_demotes_or_resets_progress(edu):
    from app.education.onboarding import answer_onboarding, start_onboarding

    edu.ensure_user("u2", level=3)
    plan = build_or_update_plan(edu, "u2", level=3)
    lesson_id = plan["lessons"][0]["id"]
    stored = edu.get_plan("u2")
    progress = {**stored["progress"], lesson_id: LessonStatus.COMPLETED.value}
    edu.upsert_plan("u2", 3, stored["lesson_ids"], progress)

    started = start_onboarding(edu, "u2")
    q, result = started["question"], None
    while q is not None:
        full = edu.get_question(q["id"])
        wrong = next(o for o in full["options"] if o != full["answer"])
        resp = answer_onboarding(edu, "u2", started["session_id"], q["id"], wrong, 50)
        q, result = resp["next_question"], resp["result"]
    assert result is not None
    assert edu.get_user_level("u2") == 3  # all-wrong retake cannot demote
    assert edu.get_plan("u2")["progress"][lesson_id] == LessonStatus.COMPLETED.value


# ---- 6. nasdaq --------------------------------------------------------------


def _answers(correct: list[bool], conf: int) -> tuple[nasdaq.Challenge, list[dict]]:
    key = {f"q{i}": "A" for i in range(1, len(correct) + 1)}
    given = [
        {"question_id": f"q{i}", "answer": "A" if ok else "B", "confidence": conf}
        for i, ok in enumerate(correct, 1)
    ]
    return nasdaq.Challenge("u", key), given


def test_nasdaq_all_wrong_at_fifty_percent_fails_despite_brier_at_limit():
    challenge, given = _answers([False] * 4, 50)
    result = nasdaq.score(challenge, given)
    assert result["brier"] == 0.25 and result["passed"] is False


def test_nasdaq_pass_needs_accuracy_and_brier():
    assert nasdaq.score(*_answers([True] * 4, 90))["passed"] is True
    assert nasdaq.score(*_answers([True] * 3 + [False], 60))["passed"] is True
    assert nasdaq.score(*_answers([True] * 2 + [False] * 2, 50))["passed"] is False


def test_gate_requires_accuracy_floor():
    user = type("U", (), {"id": "x", "level": 4})()
    assert "accuracy_gte_70" in missing_requirements(user, GateInputs(100, 0.2, 40.0))
    assert missing_requirements(user, GateInputs(100, 0.2, 80.0)) == []


def test_challenge_issue_is_capped_per_user(db_session: Session):
    uid = str(uuid.uuid4())
    EducationRepository(db_session).ensure_user(uid, level=4)
    qs = [{"id": "q1", "text": "t", "options": ["A", "B"], "_answer": "A"}]
    for _ in range(nasdaq.MAX_ACTIVE_CHALLENGES):
        nasdaq.issue(db_session, uid, qs)
    with pytest.raises(AppError) as err:
        nasdaq.issue(db_session, uid, qs)
    assert err.value.status_code == 429


# ---- 7. daily job -----------------------------------------------------------


class _Market:
    def prices(self, symbol, start, end):
        if symbol == "BAD":
            raise RuntimeError("provider down")
        idx = pd.bdate_range(start, end)
        close = [100.0 + i * 3 for i in range(len(idx))]
        return pd.DataFrame(
            {
                "close": close,
                "open": close,
                "high": [c + 1 for c in close],
                "low": [c - 1 for c in close],
                "volume": 5000.0,
            },
            index=idx,
        )

    def index(self, name, start, end):
        idx = pd.bdate_range(start, end)
        return pd.DataFrame(
            {"close": 100.0, "open": 100.0, "high": 100.0, "low": 100.0}, index=idx
        )


def _seed_claim(db: Session, symbol: str, **levels: float) -> None:
    source = Source(platform="telegram", handle=f"h-{symbol}", data_origin="real")
    db.add(source)
    db.flush()
    sub = Submission(
        user_id=uuid.uuid4(),
        source_id=source.id,
        raw_content=symbol,
        content_hash=uuid.uuid4().hex,
        captured_at=datetime(2025, 1, 20, tzinfo=UTC),
        data_origin="real",
    )
    db.add(sub)
    db.flush()
    db.add(
        Claim(
            submission_id=sub.id,
            symbol=symbol,
            direction="up",
            window_days=5,
            scorable=True,
            status="open",
            rating_eligible=True,
            data_origin="real",
            **levels,
        )
    )


def test_one_claim_failure_does_not_abort_other_claims(vsessions):
    with vsessions.begin() as db:
        _seed_claim(db, "BAD")
        _seed_claim(db, "GOOD")
    core = VerifierCore(
        complete=lambda *a, **k: {},
        check_output=lambda t: type("G", (), {"text": t, "ok": True})(),
        market=_Market(),
    )
    failures: list[str] = []
    scored = _score_open_claims(
        vsessions, core, as_of=datetime(2025, 6, 1).date(), failures=failures
    )
    assert scored == 1 and len(failures) == 1
    with vsessions() as db:
        statuses = {c.symbol: c.status for c in db.scalars(select(Claim))}
    assert statuses == {"BAD": "open", "GOOD": "scored"}


def test_platform_core_declares_nominal_basis_and_target_stop_is_scored(
    vsessions, monkeypatch
):
    monkeypatch.delenv("VERIFIER_NOMINAL_PRICE_BASIS", raising=False)
    base = platform_core()
    assert base.nominal_price_basis is not None
    assert base.nominal_price_basis(
        "TCS", datetime(2025, 1, 1).date(), datetime(2025, 2, 1).date()
    )
    with vsessions.begin() as db:
        _seed_claim(db, "GOOD", entry=100.0, target=110.0, stop=90.0)
    core = VerifierCore(
        complete=base.complete,
        check_output=base.check_output,
        market=_Market(),
        nominal_price_basis=base.nominal_price_basis,
    )
    assert _score_open_claims(vsessions, core, as_of=datetime(2025, 6, 1).date()) == 1
    monkeypatch.setenv("VERIFIER_NOMINAL_PRICE_BASIS", "false")
    assert not platform_core().nominal_price_basis(
        "TCS", datetime(2025, 1, 1).date(), datetime(2025, 2, 1).date()
    )


def test_daily_job_records_failed_run_and_skips_scoring_when_refresh_fails(db_session):
    from infra.scripts.daily_job import run_daily_job

    from app.core.models import JobRunRecord

    def boom() -> dict[str, Any]:
        raise RuntimeError("yfinance down")

    called: list[int] = []
    summary = run_daily_job(
        db=db_session, refresh_fn=boom, scoring_fn=lambda s: called.append(1) or {}
    )
    assert summary["status"] == "failed" and called == []
    assert summary["claim_scoring"]["reason"] == "market_refresh_failed"
    row = db_session.scalar(select(JobRunRecord).order_by(JobRunRecord.id.desc()))
    assert (
        row is not None
        and row.status == "failed"
        and "yfinance down" in row.details_json
    )


def test_daily_job_records_failed_run_when_scoring_raises(db_session):
    from infra.scripts.daily_job import run_daily_job

    from app.core.models import JobRunRecord

    def scoring(session: Session | None) -> dict[str, Any]:
        raise RuntimeError("scoring blew up")

    summary = run_daily_job(
        db=db_session,
        refresh_fn=lambda: {"status": "ok", "as_of": "2026-11-20"},
        scoring_fn=scoring,
    )
    assert summary["status"] == "failed"
    assert summary["claim_scoring"]["status"] == "error"
    row = db_session.scalar(select(JobRunRecord).order_by(JobRunRecord.id.desc()))
    assert row is not None and row.status == "failed"


# ---- 8. extraction timestamps ----------------------------------------------


def test_video_evidence_timestamps_never_use_a_missing_find():
    evidence = "TCS will rise; target 120; stop 90."
    segments = [
        {"start_s": 1, "end_s": 2, "text": "intro " * 16},
        {"start_s": 40, "end_s": 50, "text": evidence},
        {"start_s": 90, "end_s": 99, "text": "filler " * 800},
    ]
    calls = {"n": 0}

    def complete(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls["n"] += 1
        return {"claims": [parsed(evidence=evidence)] if calls["n"] == 2 else []}

    claims = extract_video_claims(segments, v2_core(complete))
    assert calls["n"] >= 2
    hit = next(c for c in claims if c.symbol == "TCS")
    assert (hit.evidence_start_s, hit.evidence_end_s) == (40.0, 50.0)
