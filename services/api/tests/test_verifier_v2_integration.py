"""Grounded multi-claim capture, private scores, display-only mentions and migration."""

from contextlib import nullcontext
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.guardrails import check_output
from app.core.models import UserRecord
from app.core.transcribe import Transcript
from app.core.web_search import SearchResult
from app.verifier import ingestion
from app.verifier import service as service_module
from app.verifier.extraction import extract_video_claims
from app.verifier.ingestion import CapturedTip
from app.verifier.models import (
    Base,
    Claim,
    Source,
    SourceMention,
    SourceRatingHistory,
    Submission,
)
from app.verifier.ports import VerifierCore
from app.verifier.repository import update_rating
from app.verifier.router import create_router
from app.verifier.service import VerifierService
from tests.test_verifier_persistence import persistence_engine  # noqa: F401

POSTED = datetime(2025, 1, 20, tzinfo=UTC)
VIDEO = "https://www.youtube.com/watch?v=abcdefghijk"


def parsed(symbol="TCS", direction="up", target=120.0, stop=90.0, evidence=None):
    return dict(
        symbol=symbol,
        direction=direction,
        target=target,
        stop=stop,
        entry=None,
        window=None,
        confidence=0.95,
        evidence=evidence or "TCS will rise; target 120; stop 90.",
    )


def transcript():
    return Transcript.model_validate(
        {
            "segments": [
                {
                    "start_s": 5,
                    "end_s": 15,
                    "text": "TCS will rise; target 120; stop 90.",
                },
                {
                    "start_s": 60,
                    "end_s": 70,
                    "text": "INFY will fall; target 80; stop 110.",
                },
            ],
            "language": "en",
        }
    )


class Market:
    def prices(self, symbol, start, end):
        return pd.DataFrame(
            {"close": 100.0, "open": 100.0, "volume": 5000.0},
            index=pd.bdate_range(start, end),
        )

    def index(self, name, start, end):
        return self.prices(name, start, end)

    def resolve_symbol(self, name):
        return name.upper()

    def surveillance(self, symbol, day):
        return None

    def sebi_registered(self, name):
        return {"found": None, "reg_no": None, "type": None}


def core(complete=None, search=None):
    return VerifierCore(
        complete
        or (
            lambda *a, **k: {
                "claims": [
                    parsed(),
                    parsed(
                        "INFY",
                        "down",
                        80.0,
                        110.0,
                        "INFY will fall; target 80; stop 110.",
                    ),
                ]
            }
        ),
        check_output,
        Market(),
        web_search=search,
    )


@pytest.mark.parametrize("captions", [True, False])
def test_caption_and_missing_caption_paths_preserve_offsets(monkeypatch, captions):
    from youtube_transcript_api import TranscriptsDisabled

    called = []
    client = SimpleNamespace(
        watch_html=b'<meta itemprop="datePublished" content="2025-01-20T00:00:00Z">'
    )
    monkeypatch.setattr(ingestion, "_YouTubeSession", lambda _: nullcontext(client))
    monkeypatch.setattr(ingestion, "_youtube_author", lambda *_: "@channel")

    class API:
        def __init__(self, **kwargs):
            pass

        def list(self, video_id):
            if not captions:
                raise TranscriptsDisabled(video_id)
            return SimpleNamespace(
                find_transcript=lambda *_: SimpleNamespace(
                    fetch=lambda: [
                        SimpleNamespace(
                            text=s.text, start=s.start_s, duration=s.end_s - s.start_s
                        )
                        for s in transcript().segments
                    ]
                )
            )

    monkeypatch.setattr(ingestion, "YouTubeTranscriptApi", API)
    tip = ingestion.ingest(
        text=None,
        image_base64=None,
        url=VIDEO,
        transcribe=lambda url: called.append(url) or transcript(),
    )
    assert called == ([] if captions else [VIDEO])
    assert tip.transcript_segments[0]["start_s"] == 5
    assert tip.transcript_segments[1]["end_s"] == 70
    assert "TCS will rise" in tip.text and "INFY will fall" in tip.text
    assert tip.author_verified is False  # Preserve uploader-attribution restriction.


def test_hallucinated_transcript_claim_becomes_review_without_fields():
    segments = [s.model_dump() for s in transcript().segments]
    claims = extract_video_claims(
        segments,
        core(
            lambda *a, **k: {
                "claims": [
                    parsed(
                        "RELIANCE", evidence="RELIANCE will rise; target 120; stop 90."
                    )
                ]
            }
        ),
    )
    assert claims[0].status == "needs_review"
    assert claims[0].symbol is None and claims[0].target is None


def test_chunk_edge_cannot_hide_a_bound_stop_from_grounding():
    text = "TCS will rise; target 120; " + " " * 4000 + "stop 90."
    dropped = parsed(stop=None, evidence="TCS will rise; target 120;")
    claims = extract_video_claims(
        [{"start_s": 0, "end_s": 20, "text": text}],
        core(lambda *a, **k: {"claims": [dropped]}),
    )
    assert all(c.status == "needs_review" for c in claims)
    assert all(c.target is None for c in claims)


def test_video_retains_at_most_five_grounded_distinct_claims():
    names = ("TCS", "INFY", "RELIANCE", "HDFCBANK", "ITC", "SBIN")
    segments = [
        {
            "start_s": n * 30,
            "end_s": n * 30 + 20,
            "text": f"{symbol} will rise; target 120; stop 90." + " Context." * 600,
        }
        for n, symbol in enumerate(names)
    ]

    def complete(prompt, schema):
        claims = [
            parsed(symbol=name, evidence=f"{name} will rise; target 120; stop 90.")
            for name in names
            if f"{name} will rise" in prompt
        ]
        return {"claims": claims}

    claims = extract_video_claims(segments, core(complete))
    assert len(claims) == 5
    assert all(c.status == "open" for c in claims)
    assert len({c.symbol for c in claims}) == 5


def test_long_transcript_chunks_are_bounded_deduplicated_and_capped():
    calls = []
    segments = [
        {"start_s": 0, "end_s": 1, "text": "Context. " * 600},
        {"start_s": 2, "end_s": 3, "text": "TCS will rise; target 120; stop 90."},
    ]

    def complete(prompt, schema):
        calls.append(prompt)
        return {"claims": [parsed()]} if "TCS will rise" in prompt else {"claims": []}

    result = extract_video_claims(segments, core(complete))
    assert len(calls) >= 2
    assert len(result) == 1 and result[0].symbol == "TCS"
    assert result[0].evidence_start_s == 2


def test_api_never_leaks_quality_and_replays_all_video_claims(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'v2.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    owner = uuid4()
    with sessions.begin() as db:
        db.add(UserRecord(id=str(owner), current_level=3))
    segments = [s.model_dump() for s in transcript().segments]
    text = " ".join(s["text"] for s in segments)
    tip = CapturedTip(
        text,
        "youtube",
        "@channel",
        sha256(text.encode()).hexdigest(),
        POSTED,
        POSTED,
        VIDEO,
        False,
        segments,
    )
    monkeypatch.setattr(service_module, "ingest", lambda **kwargs: tip)
    app = FastAPI()
    app.include_router(
        create_router(
            VerifierService(sessions, core()),
            lambda: SimpleNamespace(id=owner, level=3),
        ),
        prefix="/api/v1",
    )
    with TestClient(app) as client:
        first = client.post("/api/v1/verify", json={"url": VIDEO})
        assert first.status_code == 200, first.text
        data = first.json()
        assert len(data["claims"]) == 2
        assert data["claims"][0]["evidence_start_s"] == 5
        assert data["claims"][1]["evidence_end_s"] == 70
        assert data["tip_facts"]
        again = client.post("/api/v1/verify", json={"url": VIDEO})
        assert [c["id"] for c in again.json()["claims"]] == [
            c["id"] for c in data["claims"]
        ]
        for response in (
            first,
            again,
            client.get("/api/v1/submissions/mine"),
            client.get(f'/api/v1/sources/{data["source"]["id"]}'),
        ):
            assert "tip_quality" not in response.text
    with sessions() as db:
        stored = list(db.scalars(select(Claim)))
        assert len(stored) == 2
        assert all(
            c.tip_quality_version == "tip-quality-v1"
            and "tip_quality_score" in c.tip_quality
            for c in stored
        )
        assert all(not c.rating_eligible for c in stored)
        assert db.scalar(select(Submission)).transcript_segments[1]["start_s"] == 60
    engine.dispose()


def test_mentions_are_private_safe_display_links_and_never_affect_rating(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mentions.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    queries = []

    def search(query, *, limit):
        queries.append(query)
        return [
            SearchResult(
                url="https://example.org/discussion",
                title="Public discussion",
                snippet="buy TCS now",
            ),
            SearchResult(url="https://example.org/advice", title="Buy TCS now"),
        ]

    service = VerifierService(sessions, core(search=search))
    with sessions.begin() as db:
        source = Source(platform="telegram", handle="fixture-desk", data_origin="real")
        db.add(source)
        db.flush()
        update_rating(db, source)
        sid, initial = source.id, source.score
    profile = service.source(uuid4(), sid)
    assert queries == ['"fixture-desk" "telegram"']
    assert len(profile.mentions) == 1
    service.source(uuid4(), sid)
    assert len(queries) == 1  # Stored mentions also respect the 24-hour refresh bound.
    assert (
        "snippet" not in profile.model_dump_json()
        and "buy TCS" not in profile.model_dump_json()
    )
    with sessions() as db:
        assert db.get(Source, sid).score == initial
        assert (
            db.scalar(
                select(SourceRatingHistory).order_by(
                    SourceRatingHistory.changed_at.desc()
                )
            ).formula_version
            == "source-v2-q0"
        )
        assert len(list(db.scalars(select(SourceMention)))) == 1
    engine.dispose()


def test_v2_migration_roundtrip(persistence_engine):  # noqa: F811
    from pathlib import Path

    engine = persistence_engine
    repo_root = Path(__file__).resolve().parents[3]
    cfg = Config(str(repo_root / "db/alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "db/migrations"))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        assert "tip_quality" in {
            c["name"] for c in inspect(connection).get_columns("claims")
        }
        # Relative -1 is ambiguous at a merge point; name the shared parent
        # and exercise both branches rather than only removing the merge marker.
        command.downgrade(cfg, "20261121_submission_owner_fk")
        assert "tip_quality" not in {
            c["name"] for c in inspect(connection).get_columns("claims")
        }
        command.upgrade(cfg, "head")
        assert inspect(connection).has_table("source_mentions")
        assert not any(
            c["column_names"] == ["submission_id"]
            for c in inspect(connection).get_unique_constraints("claims")
        )
        with Session(connection) as db:
            owner = uuid4()
            db.add(UserRecord(id=str(owner), current_level=3))
            source = Source(
                platform="telegram", handle="migration-fixture", data_origin="synthetic"
            )
            db.add(source)
            db.flush()
            submission = Submission(
                user_id=owner,
                source_id=source.id,
                raw_content="Fixture",
                content_hash="a" * 64,
                captured_at=POSTED,
                data_origin="synthetic",
            )
            db.add(submission)
            db.flush()
            for _ in range(2):
                db.add(
                    Claim(
                        submission_id=submission.id,
                        window_days=20,
                        status="needs_review",
                        scorable=False,
                        data_origin="synthetic",
                    )
                )
            db.flush()
            with pytest.raises(RuntimeError, match="Reconcile multi-claim"):
                command.downgrade(cfg, "20261121_submission_owner_fk")
            assert len(list(db.scalars(select(Claim)))) == 2
            assert inspect(connection).has_table("source_mentions")
