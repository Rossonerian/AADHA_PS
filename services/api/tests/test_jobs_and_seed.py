"""Tests for `infra/scripts/seed.py`, `daily_job.py`, and `smoke_test.py`."""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import JobRunRecord, UserRecord
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_seed_validates_real_seed_directory_and_records_job_run(
    db_session: Session,
) -> None:
    """`seed.py` validates `data/seed/`, loads Education content only, and logs `job_runs`."""
    from infra.scripts.seed import seed

    summary = seed(db=db_session)
    assert summary["status"] == "ok"
    assert summary["files_validated"] >= 44
    assert summary["records_validated"] > 1000
    assert summary["data_origins"] == ["real", "synthetic"]
    assert summary["content_loaded"] == {
        "questions": 120,
        "lessons": 12,
        "scenarios": 24,
        "explain_records": 30,
    }
    assert summary["market_data_as_of"] is not None
    assert summary["db_recorded"] is True
    # Content-only seeding must never insert fake or demo users.
    assert db_session.query(UserRecord).count() == 0

    row = db_session.scalar(
        select(JobRunRecord)
        .where(JobRunRecord.job_name == "seed")
        .order_by(JobRunRecord.id.desc())
    )
    assert row is not None
    assert row.status == "ok"
    assert row.market_data_as_of == summary["market_data_as_of"]


def test_seed_rejects_missing_data_origin(tmp_path: Path) -> None:
    """`seed.py` fails fast when any CSV row lacks valid `data_origin`."""
    from infra.scripts.seed import seed

    market_dir = tmp_path / "market"
    market_dir.mkdir(parents=True)
    (market_dir / "sebi_ra_ia.csv").write_text(
        "reg_no,type,name,status,data_origin\n"
        "INH000000412,RA,Motilal Oswal,active,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="data_origin"):
        seed(seed_dir=tmp_path)


def test_daily_job_executes_refresh_and_scoring_and_logs_job_run(
    db_session: Session,
) -> None:
    """`daily_job.py` runs market refresh + claim scoring and inserts `job_runs` row."""
    from infra.scripts.daily_job import run_daily_job

    def _mock_refresh() -> dict[str, Any]:
        return {
            "status": "ok",
            "as_of": "2026-11-20",
            "symbols_cached": 35,
            "indices_cached": 2,
            "failed": [],
        }

    summary = run_daily_job(db=db_session, refresh_fn=_mock_refresh)
    assert summary["status"] == "ok"
    assert summary["market_data_as_of"] == "2026-11-20"
    assert summary["claim_scoring"] == {"status": "ok", "scored": 0}
    assert summary["db_recorded"] is True

    row = db_session.scalar(
        select(JobRunRecord)
        .where(JobRunRecord.job_name == "daily_job")
        .order_by(JobRunRecord.id.desc())
    )
    assert row is not None
    assert row.status == "ok"
    assert row.market_data_as_of == "2026-11-20"
    details = json.loads(row.details_json)
    assert details["market_refresh"]["symbols_cached"] == 35


def test_smoke_test_platform_only_against_asgi_app(
    migrated_db: str,
    make_jwt: Callable[..., str],
) -> None:
    """`smoke_test.py --platform-only` passes `/health` + `/me` (401 & 200) via TestClient."""
    from infra.scripts.smoke_test import run_smoke_test

    del migrated_db
    app = create_app()
    token = make_jwt(
        str(uuid.uuid4()),
        email="smoke@example.com",
        user_metadata={"full_name": "Smoke Test User"},
    )
    with TestClient(app, base_url="http://testserver/api/v1") as client:
        result = run_smoke_test(
            base_url="http://testserver/api/v1",
            jwt_token=token,
            platform_only=True,
            http_client=client,
        )

    assert result["status"] == "ok"
    assert result["mode"] == "platform-only"
    assert [c["step"] for c in result["checks"]] == [
        "health",
        "me_unauthenticated_401",
        "me_authenticated",
    ]


def test_smoke_test_health_only_against_asgi_app(migrated_db: str) -> None:
    """`smoke_test.py --health-only` verifies `/health` and `/me` 401 without a JWT."""
    from infra.scripts.smoke_test import run_smoke_test

    del migrated_db
    app = create_app()
    with TestClient(app, base_url="http://testserver/api/v1") as client:
        result = run_smoke_test(
            base_url="http://testserver",
            health_only=True,
            http_client=client,
        )

    assert result["status"] == "ok"
    assert result["mode"] == "health-only"
    assert result["base_url"] == "http://testserver/api/v1"
    assert [c["step"] for c in result["checks"]] == [
        "health",
        "me_unauthenticated_401",
    ]


def test_smoke_test_fails_on_stale_market_data(
    migrated_db: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`smoke_test.py` fails fast when `market_data_as_of` exceeds `max_stale_days`."""
    from infra.scripts.smoke_test import run_smoke_test

    del migrated_db
    monkeypatch.setattr("app.main.get_market_data_as_of", lambda: "2020-01-01")
    app = create_app()
    with (
        TestClient(app, base_url="http://testserver/api/v1") as client,
        pytest.raises(RuntimeError, match="stale"),
    ):
        run_smoke_test(
            base_url="http://testserver/api/v1",
            health_only=True,
            max_stale_days=5,
            http_client=client,
        )


def test_smoke_test_full_walkthrough_against_asgi_app(
    db_session: Session,
    make_jwt: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`smoke_test.py` walks the full end-to-end learning and verify path."""
    from infra.scripts.seed import seed
    from infra.scripts.smoke_test import run_smoke_test

    from tests.education._market_seed import use_education_price_seed

    seed(db=db_session)
    cleanup_prices = use_education_price_seed()

    def _mock_complete(
        prompt: str,
        schema: object = None,
        **_kwargs: object,
    ) -> dict[str, Any]:
        del prompt, schema
        return {
            "symbol": "RELIANCE",
            "direction": "up",
            "entry": None,
            "target": 1600.0,
            "stop": 1200.0,
            "window": None,
            "confidence": 0.85,
            "evidence": "RELIANCE buy karo target 1600 SL 1200 guaranteed 20% return",
        }

    monkeypatch.setattr("app.core.llm.complete", _mock_complete)
    token = make_jwt(
        str(uuid.uuid4()),
        email="full-smoke@example.com",
        user_metadata={"full_name": "Full Smoke User"},
    )
    app = create_app()
    try:
        with TestClient(app, base_url="http://testserver/api/v1") as client:
            result = run_smoke_test(
                base_url="http://testserver/api/v1",
                jwt_token=token,
                platform_only=False,
                http_client=client,
            )
    finally:
        cleanup_prices()

    assert result["status"] == "ok"
    assert result["mode"] == "full"
    assert [c["step"] for c in result["checks"]] == [
        "health",
        "me_unauthenticated_401",
        "me_authenticated",
        "onboarding",
        "plan_and_lesson",
        "scenarios",
        "explain",
        "verify",
        "dashboard",
    ]
    steps = {c["step"]: c for c in result["checks"]}
    assert steps["onboarding"]["level"] == 4
    assert steps["dashboard"]["level"] == 4
