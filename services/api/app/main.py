"""FastAPI application entrypoint and core platform routes."""

from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.auth import User, current_user
from app.core.config import get_settings
from app.core.db import check_db_health, get_db
from app.core.errors import register_exception_handlers
from app.core.logging import RequestLoggingMiddleware
from app.core.market import get_market_data_as_of
from app.education.router import router as education_router
from app.education.unlocks import get_user_unlocks
from app.nasdaq_verifier.gate import missing_requirements, read_gate_inputs
from app.nasdaq_verifier.router import router as nasdaq_router
from app.verifier.router import router as verifier_router


def create_app() -> FastAPI:
    """Construct and configure the Aacharya FastAPI application."""
    current_settings = get_settings()

    application = FastAPI(
        title="Aacharya API",
        version=current_settings.app_version,
    )

    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=current_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)

    @application.get("/api/v1/health", tags=["platform"])
    def health() -> dict[str, Any]:
        db_status = check_db_health()
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "version": get_settings().app_version,
            "db": db_status,
            "market_data_as_of": get_market_data_as_of(),
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
