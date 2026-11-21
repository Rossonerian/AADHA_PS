"""FastAPI application entrypoint and core platform routes."""

from datetime import UTC, datetime
from datetime import date as DateType
from typing import Any

from fastapi import Depends, FastAPI, Response
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
from app.profiles.router import router as profiles_router
from app.profiles.schemas import UserProfileOut
from app.profiles.service import get_or_create_profile
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
    # Compare in UTC so the age does not depend on the host's local timezone.
    age_days = (datetime.now(UTC).date() - as_of_date).days
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

    # Interactive docs and the schema are not exposed in production.
    docs_enabled = not current_settings.is_production
    application = FastAPI(
        title="PaisaProof API",
        version=current_settings.app_version,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(RequestSizeLimitMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=current_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    register_exception_handlers(application)
    register_education_exception_handlers(application)

    @application.get("/api/v1/health", tags=["platform"])
    @application.get("/health", tags=["platform"], include_in_schema=False)
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

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, Any]:
        settings = get_settings()
        return {
            "name": "PaisaProof API",
            "status": "ok",
            "version": settings.app_version,
            "web_url": "https://paisaproof.vercel.app",
            "health": "/api/v1/health",
        }

    @application.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    @application.get("/api/v1/me", tags=["platform"])
    def read_me(
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        unlocks = get_user_unlocks(db, user.id, user.level)
        if not missing_requirements(user, read_gate_inputs(db, user)):
            unlocks = [*unlocks, "nasdaq_verifier"]
        profile_record = get_or_create_profile(db, user.id, fallback_name=user.name)
        return {
            "id": user.id,
            "name": profile_record.display_name or user.name,
            "level": user.level,
            "unlocks": unlocks,
            "profile": UserProfileOut.model_validate(profile_record).model_dump(
                mode="json"
            ),
            "onboarding_completed": profile_record.onboarding_completed_at is not None,
            "data_origin": "real",
        }

    application.include_router(education_router, prefix="/api/v1")
    application.include_router(profiles_router, prefix="/api/v1")
    application.include_router(verifier_router, prefix="/api/v1")
    application.include_router(nasdaq_router, prefix="/api/v1")

    return application


app = create_app()
