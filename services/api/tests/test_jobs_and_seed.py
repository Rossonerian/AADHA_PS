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

from app.core.models import JobRunRecord
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_seed_validates_real_seed_directory_and_records_job_run(
    db_session: Session,
) -> None:
    """`seed.py` validates `data/seed/` records (`data_origin`) and logs `job_runs`."""
    from infra.scripts.seed import seed

    summary = seed(db=db_session)
    assert summary["status"] == "ok"
    assert summary["files_validated"] >= 40
    assert summary["records_validated"] > 1000
    assert summary["data_origins"] == ["real"]
    assert summary["market_data_as_of"] is not None
    assert summary["db_recorded"] is True

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
