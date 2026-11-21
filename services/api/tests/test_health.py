"""Tests for Alembic initial migration and `/api/v1/health`."""

import os
import subprocess
import sys
from datetime import date as DateType
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.core.market import get_market_data_as_of

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_alembic_upgrade_head_on_fresh_sqlite(tmp_path: Path) -> None:
    """Running `alembic -c db/alembic.ini upgrade head` creates `users` and `job_runs`."""
    db_path = tmp_path / "alembic_cli_test.db"
    db_url = f"sqlite:///{db_path}"

    alembic_bin = Path(sys.executable).with_name("alembic")
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PYTHONPATH"] = str(REPO_ROOT / "services" / "api")

    result = subprocess.run(
        [str(alembic_bin), "-c", "db/alembic.ini", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic failed: {result.stderr}\n{result.stdout}"

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"users", "job_runs", "alembic_version"}.issubset(tables)

        user_cols = {col["name"] for col in inspector.get_columns("users")}
        assert {"id", "name", "current_level", "created_at"}.issubset(user_cols)

        job_cols = {col["name"] for col in inspector.get_columns("job_runs")}
        assert {
            "id",
            "job_name",
            "status",
            "market_data_as_of",
            "details_json",
            "ran_at",
        }.issubset(job_cols)
    finally:
        engine.dispose()


def test_health_endpoint_ok(client: TestClient) -> None:
    """GET /api/v1/health returns 200 with db='ok' and market_data_as_of."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers

    payload = response.json()
    expected_as_of = get_market_data_as_of()
    assert isinstance(expected_as_of, str) and expected_as_of
    DateType.fromisoformat(expected_as_of)
    assert payload == {
        "status": "ok",
        "version": get_settings().app_version,
        "db": "ok",
        "market_data_as_of": expected_as_of,
    }


def test_health_endpoint_degraded_when_db_check_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/v1/health reports status='degraded' when DB probe returns 'error'."""
    monkeypatch.setattr("app.main.check_db_health", lambda: "error")

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["db"] == "error"


def test_stale_market_warning_uses_utc_date(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    from app import main as main_module

    warnings: list[str] = []
    monkeypatch.setattr(
        main_module._logger, "warning", lambda msg, *a, **k: warnings.append(msg)
    )
    today = datetime.now(UTC).date()
    main_module._warn_if_market_data_stale(today.isoformat(), 5)
    assert warnings == []
    main_module._warn_if_market_data_stale((today - timedelta(days=9)).isoformat(), 5)
    assert warnings == ["market_data_stale"]


def _app_with_env(monkeypatch, **env: str):
    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        return create_app()
    finally:
        get_settings.cache_clear()


def test_production_disables_docs_and_fails_closed_on_cors(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    app = _app_with_env(monkeypatch, APP_ENV="production")
    client = TestClient(app)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
    preflight = client.options(
        "/api/v1/me",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in preflight.headers


def test_non_production_keeps_docs_and_dev_cors(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    client = TestClient(_app_with_env(monkeypatch, APP_ENV="local"))
    assert client.get("/openapi.json").status_code == 200
    preflight = client.options(
        "/api/v1/me",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_explicit_cors_origins_used_in_production(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    app = _app_with_env(
        monkeypatch, APP_ENV="production", CORS_ORIGINS="https://app.example.com"
    )
    preflight = TestClient(app).options(
        "/api/v1/me",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.headers["access-control-allow-origin"] == "https://app.example.com"
