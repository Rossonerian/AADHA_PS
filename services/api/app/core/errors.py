"""Canonical API exceptions and FastAPI exception handlers."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

_logger = get_logger("paisaproof.errors")

_HTTP_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


class AppError(Exception):
    """Base structured error returned as `{error: {code, message, ...}}`."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.extra: dict[str, Any] = dict(extra) if extra else {}
        self.headers: dict[str, str] | None = None
        super().__init__(message)


class UnauthorizedError(AppError):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(
        self,
        message: str = "Authentication required",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="UNAUTHORIZED", message=message, status_code=401, extra=extra
        )


class ToolLockedError(AppError):
    """Raised when the user's level is below the required tool unlock level."""

    def __init__(self, required_level: int, message: str | None = None) -> None:
        resolved_message = message or f"This tool unlocks at level {required_level}"
        super().__init__(
            code="TOOL_LOCKED",
            message=resolved_message,
            status_code=403,
            extra={"required_level": required_level},
        )


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        message: str = "Resource not found",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="NOT_FOUND", message=message, status_code=404, extra=extra
        )


class ExternalServiceError(AppError):
    """Raised when an upstream provider call fails."""

    def __init__(
        self,
        message: str = "External service error",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="EXTERNAL_SERVICE_ERROR",
            message=message,
            status_code=502,
            extra=extra,
        )


class ConfigurationError(AppError):
    """Raised when required server configuration is missing or invalid."""

    def __init__(
        self,
        message: str = "Server configuration error",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="CONFIGURATION_ERROR",
            message=message,
            status_code=500,
            extra=extra,
        )


def _error_json(
    status_code: int,
    code: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    error_body: dict[str, Any] = {"code": code, "message": message}
    if extra:
        error_body.update(extra)
    return JSONResponse(status_code=status_code, content={"error": error_body})


def register_exception_handlers(app: FastAPI) -> None:
    """Register unified JSON error handlers on the FastAPI application."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        response = _error_json(exc.status_code, exc.code, exc.message, exc.extra)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _HTTP_STATUS_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        extra = {"detail": exc.detail} if not isinstance(exc.detail, str) else None
        return _error_json(exc.status_code, code, message, extra)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if _request.url.path.rstrip("/") in {
            "/api/v1/verify",
            "/api/v1/nasdaq-verifier/submit",
        }:
            # Pydantic errors include input values (and arbitrary extra-field names).
            # Never echo submitted tips, injected instructions or phone numbers.
            return _error_json(422, "VALIDATION_ERROR", "Request validation failed")
        return _error_json(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            extra={"details": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        _logger.exception(
            "unhandled_exception",
            extra={"method": request.method, "path": request.url.path},
            exc_info=exc,
        )
        return _error_json(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        )
