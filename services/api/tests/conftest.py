"""Shared pytest fixtures for the PaisaProof API test suite."""

import os
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import configure_engine, get_engine, get_session_factory
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI_PATH = REPO_ROOT / "db" / "alembic.ini"
TEST_JWT_SECRET = "test-supabase-jwt-secret-at-least-32-bytes"


@pytest.fixture(autouse=True)
def _reset_rate_limit_state() -> Generator[None, None, None]:
    """Reset the global rate limiter around each test for strict test isolation."""
    reset_rate_limiter()
    yield
    reset_rate_limiter()


@pytest.fixture
def jwt_secret() -> str:
    """Return deterministic HS256 test secret (>=32 bytes)."""
    return TEST_JWT_SECRET


@pytest.fixture
def migrated_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, jwt_secret: str
) -> Generator[str, None, None]:
    """Provision an isolated SQLite DB, run Alembic migrations, and configure the engine."""
    db_file = tmp_path / "test_paisaproof.db"
    db_url = f"sqlite:///{db_file}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()

    alembic_cfg = Config(str(ALEMBIC_INI_PATH))
    previous_cwd = os.getcwd()
    try:
        os.chdir(REPO_ROOT)
        command.upgrade(alembic_cfg, "head")
    finally:
        os.chdir(previous_cwd)

    configure_engine(db_url)
    try:
        yield db_url
    finally:
        get_engine().dispose()
        get_settings.cache_clear()


@pytest.fixture
def db_session(migrated_db: str) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session bound to the isolated migrated test database."""
    del migrated_db
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(migrated_db: str) -> Generator[TestClient, None, None]:
    """Return a FastAPI TestClient wired to the isolated migrated test database."""
    del migrated_db
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def make_jwt(jwt_secret: str) -> Callable[..., str]:
    """Factory fixture producing signed Supabase-shaped HS256 JWT tokens."""

    def _make_jwt(
        sub: str,
        *,
        secret: str | None = None,
        exp_delta_seconds: int = 3600,
        aud: str = "authenticated",
        email: str | None = "user@example.com",
        user_metadata: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(tz=UTC)
        payload: dict[str, Any] = {
            "sub": sub,
            "aud": aud,
            "role": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=exp_delta_seconds)).timestamp()),
        }
        if email is not None:
            payload["email"] = email
        if user_metadata is not None:
            payload["user_metadata"] = user_metadata
        return jwt.encode(payload, secret or jwt_secret, algorithm="HS256")

    return _make_jwt
