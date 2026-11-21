"""Recompute the shipped public corpus and exercise its fail-closed import gate."""

import importlib.util
import json
import shutil
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.models import UserRecord
from app.verifier.models import Claim, Source, Submission
from app.verifier.real_seed import SEED_OWNER, load_bundle, validate_bundle

BUNDLE = Path(__file__).resolve().parents[3] / "data/seed/verifier/real"


def test_real_corpus_recomputes_without_network_or_llm():
    validated = validate_bundle(BUNDLE)
    counts = Counter(record.publisher for record, _ in validated)
    assert len(counts) >= 30 and min(counts.values()) >= 5
    assert len(validated) >= 150
    assert {score.method for _, score in validated} == {"benchmark_relative"}
    assert all(score.correct is not None for _, score in validated)
    published = json.loads((BUNDLE / "claims.json").read_text(encoding="utf-8"))
    for row, (_, score) in zip(published, validated, strict=True):
        assert row["outcome"]["correct"] == score.correct
        assert row["outcome"]["window_end"] == str(score.window_end)
        assert row["outcome"]["stock_pct"] == pytest.approx(score.stock_pct, abs=1e-10)
        assert row["outcome"]["index_pct"] == pytest.approx(score.index_pct, abs=1e-10)


def test_import_is_idempotent_and_keeps_real_provenance(db_session):
    sessions = sessionmaker(db_session.get_bind())
    first = load_bundle(sessions, BUNDLE)
    with sessions.begin() as db:
        # Reproduce a legacy import that selected an obsolete price field.
        legacy = db.scalar(select(Claim).limit(1))
        legacy_id = legacy.id
        legacy.target = 1.0
        legacy.direction = "down" if legacy.direction == "up" else "up"
    second = load_bundle(sessions, BUNDLE)
    assert first == second
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Source)) == 30
        assert db.scalar(select(func.count()).select_from(Claim)) == 150
        assert db.scalar(select(func.count()).select_from(Submission)) == 150
        assert set(db.scalars(select(Claim.data_origin))) == {"real"}
        assert set(db.scalars(select(Submission.user_id))) == {SEED_OWNER}
        assert db.get(UserRecord, str(SEED_OWNER)).current_level == 1
        assert all(source.scored_claims == 5 for source in db.scalars(select(Source)))
        for submission in db.scalars(select(Submission)):
            assert "Document SHA256:" in submission.raw_content
            assert submission.post_url.startswith("https://")
        restored = db.get(Claim, legacy_id)
        assert restored.target != 1.0
        expected = {str(record.url): record for record, _ in validate_bundle(BUNDLE)}
        for submission, claim in db.execute(
            select(Submission, Claim).join(Claim, Claim.submission_id == Submission.id)
        ):
            assert claim.target == expected[submission.post_url].target
            assert claim.direction == expected[submission.post_url].direction


def test_report_parser_ignores_previous_target_and_preserves_ranged_horizons():
    path = BUNDLE.parents[3] / "infra/scripts/review_verifier_sources.py"
    spec = importlib.util.spec_from_file_location("review_public_reports", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = "Previous TP 90. Revised target price of Rs 140."
    target, _ = module.quoted_number(text, r"target\s+price|TP")
    assert target == 140
    historical = "Earlier discussion mentions a target of Rs 90.\nTarget\nRs. 140"
    assert module.quoted_number(historical, r"target\s+price|target|TP")[0] == 140
    assert module.horizon_for("Time Period: 12 months")[:2] == (240, "stated_horizon")
    assert module.horizon_for("Duration: 12-18 months")[:2] == (
        None,
        "ambiguous_source_horizon",
    )


@pytest.fixture
def altered_bundle(tmp_path):
    target = tmp_path / "real"
    shutil.copytree(BUNDLE, target)
    return target


@pytest.mark.parametrize(
    "defect", ["quota", "synthetic_claim", "duplicate_pdf", "hash"]
)
def test_bad_bundle_cannot_start_import(altered_bundle, db_session, defect):
    path = altered_bundle / "claims.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    if defect == "quota":
        rows.pop()
    elif defect == "synthetic_claim":
        rows[0]["data_origin"] = "synthetic"
    elif defect == "duplicate_pdf":
        rows[0]["sha256"] = rows[1]["sha256"]
    else:
        rows[0]["price_sha256"] = "0" * 64
    path.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises((ValueError, ValidationError)):
        load_bundle(sessionmaker(db_session.get_bind()), altered_bundle)
    assert db_session.scalar(select(func.count()).select_from(Source)) == 0
    assert db_session.get(UserRecord, str(SEED_OWNER)) is None


@pytest.mark.parametrize("defect", ["synthetic_prices", "incomplete_window"])
def test_matching_hash_does_not_make_bad_market_evidence_valid(altered_bundle, defect):
    path = altered_bundle / "claims.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    symbol = rows[0]["symbol"]
    prices = altered_bundle / "prices" / f"{symbol}.csv"
    frame = pd.read_csv(prices)
    if defect == "synthetic_prices":
        frame["data_origin"] = "synthetic"
    else:
        frame = frame.iloc[:1]
    frame.to_csv(prices, index=False)
    for row in rows:
        if row["symbol"] == symbol:
            row["price_sha256"] = sha256(prices.read_bytes()).hexdigest()
    path.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_bundle(altered_bundle)
