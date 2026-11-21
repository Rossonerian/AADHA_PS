"""FastAPI application entrypoint and core platform routes."""

from datetime import date as DateType
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.auth import User, current_user
from app.core.config import get_settings
from app.core.db import check_db_health, get_db
from app.core.errors import register_exception_handlers
from app.core.logging import RequestLoggingMiddleware, get_logger
from app.core.market import get_market_data_as_of
from app.core.rate_limit import RateLimitMiddleware, RequestSizeLimitMiddleware
from app.education.exceptions import (
    register_exception_handlers as register_education_exception_handlers,
)
from app.education.router import router as education_router
from app.education.unlocks import get_user_unlocks
from app.nasdaq_verifier.gate import missing_requirements, read_gate_inputs
from app.nasdaq_verifier.router import router as nasdaq_router
from app.verifier.router import router as verifier_router

_logger = get_logger("paisaproof.main")


def _warn_if_market_data_stale(as_of_raw: str | None, max_stale_days: int) -> None:
    if max_stale_days <= 0:
        return
    if not as_of_raw:
        _logger.warning("market_data_stale", extra={"market_data_as_of": None})
        return
    try:
        as_of_date = DateType.fromisoformat(as_of_raw[:10])
    except ValueError:
        _logger.warning("market_data_stale", extra={"market_data_as_of": as_of_raw})
        return
    age_days = (DateType.today() - as_of_date).days
    if age_days > max_stale_days:
        _logger.warning(
            "market_data_stale",
            extra={
                "market_data_as_of": as_of_raw,
                "age_days": age_days,
                "max_stale_days": max_stale_days,
            },
        )


def create_app() -> FastAPI:
    """Construct and configure the PaisaProof FastAPI application."""
    current_settings = get_settings()

    application = FastAPI(
        title="PaisaProof API",
        version=current_settings.app_version,
    )

    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(RequestSizeLimitMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=current_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    register_education_exception_handlers(application)

    @application.get("/api/v1/health", tags=["platform"])
    def health() -> dict[str, Any]:
        settings = get_settings()
        db_status = check_db_health()
        market_as_of = get_market_data_as_of()
        _warn_if_market_data_stale(market_as_of, settings.market_data_max_stale_days)
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "version": settings.app_version,
            "db": db_status,
            "market_data_as_of": market_as_of,
        }

    @application.get("/api/v1/me", tags=["platform"])
    def read_me(
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        unlocks = get_user_unlocks(db, user.id, user.level)
        if not missing_requirements(user, read_gate_inputs(db, user)):
            unlocks = [*unlocks, "nasdaq_verifier"]
        return {
            "id": user.id,
            "name": user.name,
            "level": user.level,
            "unlocks": unlocks,
        }

    application.include_router(education_router, prefix="/api/v1")
    application.include_router(verifier_router, prefix="/api/v1")
    application.include_router(nasdaq_router, prefix="/api/v1")

    return application


app = create_app()
