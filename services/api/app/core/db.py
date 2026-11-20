"""SQLAlchemy 2.0 engine, session management, and health check helpers."""

import os
from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings, normalize_database_url
from app.core.logging import get_logger

_logger = get_logger("paisaproof.db")


class Base(DeclarativeBase):
    """Declarative base shared across all SQLAlchemy ORM models."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_configured_url: str | None = None
_explicit_url: str | None = None


def _resolve_database_url(override_url: str | None = None) -> str:
    if override_url:
        return normalize_database_url(override_url)
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return normalize_database_url(env_url)
    return normalize_database_url(get_settings().database_url)


def _create_engine(db_url: str) -> Engine:
    kwargs: dict[str, Any] = {"future": True}
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if db_url in {"sqlite://", "sqlite:///:memory:"}:
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(db_url, **kwargs)


def configure_engine(url: str | None = None) -> Engine:
    """Configure or reconfigure the global SQLAlchemy engine and session factory."""
    global _engine, _session_factory, _configured_url, _explicit_url

    _explicit_url = normalize_database_url(url) if url else None
    resolved_url = _resolve_database_url(url)

    if _engine is not None:
        _engine.dispose()

    _engine = _create_engine(resolved_url)
    _session_factory = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    _configured_url = resolved_url
    return _engine


def get_engine() -> Engine:
    """Return the active SQLAlchemy engine, rebuilding if DATABASE_URL changed dynamically."""
    if _engine is None:
        return configure_engine(_explicit_url)

    if _explicit_url is None:
        current_url = _resolve_database_url()
        if current_url != _configured_url:
            return configure_engine()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the active SQLAlchemy sessionmaker bound to the current engine."""
    get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_db_health() -> str:
    """Execute `SELECT 1` and return `'ok'` if healthy, else `'error'`."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        _logger.warning("db_health_check_failed", extra={"error": str(exc)})
        return "error"
