"""FastAPI entry points; mount with prefix /api/v1 in the platform app."""

from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.auth import current_user as platform_current_user
from app.core.db import get_session_factory
from app.core.errors import ConfigurationError

from .extraction import AdviceRequest
from .ingestion import IngestionError
from .ports import User, platform_core
from .schemas import SourceResponse, SubmissionsResponse, VerifyRequest, VerifyResponse
from .service import SourceNotFound, VerifierService


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message}}
    )


def create_router(
    service: VerifierService, current_user: Callable[..., User]
) -> APIRouter:
    class VerifierRoute(APIRoute):
        def get_route_handler(
            self,
        ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
            handler = super().get_route_handler()

            async def handle(request: Request) -> Response:
                try:
                    return await handler(request)
                except RequestValidationError:
                    return _error(
                        422,
                        "INVALID_REQUEST",
                        service.safe_text("The request is invalid."),
                    )
                except IngestionError as exc:
                    return _error(422, exc.code, service.safe_text(str(exc)))
                except AdviceRequest as exc:
                    return _error(
                        422, "ADVICE_NOT_SUPPORTED", service.safe_text(str(exc))
                    )
                except SourceNotFound:
                    return _error(
                        404,
                        "SOURCE_NOT_FOUND",
                        service.safe_text("The source was not found."),
                    )
                except ConfigurationError:
                    return _error(
                        503,
                        "VERIFIER_UNAVAILABLE",
                        service.safe_text(
                            "Tip verification is temporarily unavailable while the "
                            "extraction service is not configured."
                        ),
                    )

            return handle

    router = APIRouter(route_class=VerifierRoute, tags=["verifier"])
    auth = Depends(current_user)

    @router.post("/verify", response_model=VerifyResponse)
    def verify(body: VerifyRequest, user: User = auth) -> VerifyResponse:
        return service.verify(UUID(str(user.id)), user.level, body)

    @router.get("/sources/{id}", response_model=SourceResponse)
    def source(id: UUID, user: User = auth) -> SourceResponse | JSONResponse:
        if user.level < 3:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "TOOL_LOCKED",
                        "message": service.safe_text("This tool unlocks at level 3."),
                        "required_level": 3,
                    }
                },
            )
        return service.source(UUID(str(user.id)), id)

    @router.get("/submissions/mine", response_model=SubmissionsResponse)
    def my_submissions(user: User = auth) -> SubmissionsResponse:
        return service.submissions(UUID(str(user.id)), user.level)

    return router


def _platform_session() -> Session:
    return get_session_factory()()


router = create_router(
    VerifierService(_platform_session, platform_core()), platform_current_user
)
