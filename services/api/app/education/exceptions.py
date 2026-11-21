"""Standardized Education exceptions and FastAPI error handlers (SoT Section 7)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class EducationError(Exception):
    """Base application error for Education endpoints."""

    def __init__(
        self, code: str, message: str, status_code: int = 400, extra: dict | None = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}


class ToolLockedError(EducationError):
    """Raised when a user tries to access a tool above their unlocked level (HTTP 403)."""

    def __init__(self, tool: str, required_level: int, current_level: int):
        super().__init__(
            code="TOOL_LOCKED",
            message=(
                f"Tool '{tool}' requires Level {required_level} "
                f"(current level: {current_level}). Complete your level-up assessment to unlock it."
            ),
            status_code=403,
            extra={"required_level": required_level, "tool": tool},
        )
        self.tool = tool
        self.required_level = required_level
        self.current_level = current_level


class NotFoundError(EducationError):
    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, status_code=404)


# Re-submitting a finished session, or answering out of order, is a state conflict.
_CONFLICT_CODES = frozenset(
    {"ASSESSMENT_ALREADY_SUBMITTED", "SESSION_COMPLETED", "QUESTION_MISMATCH"}
)


class ValidationDomainError(EducationError):
    def __init__(self, code: str, message: str):
        super().__init__(
            code=code,
            message=message,
            status_code=409 if code in _CONFLICT_CODES else 422,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers SoT Section 7 error formatters on the FastAPI app.

    SoT Section 7:
    - General errors: {error: {code, message}} with HTTP 4xx/5xx
    - Locked tool: 403 {code: "TOOL_LOCKED", required_level}
      (we also include `error: {code, message, required_level}` so both parsers work cleanly)
    """

    @app.exception_handler(ToolLockedError)
    async def _handle_tool_locked(
        _request: Request, exc: ToolLockedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "code": "TOOL_LOCKED",
                "required_level": exc.required_level,
                "error": {
                    "code": "TOOL_LOCKED",
                    "message": exc.message,
                    "required_level": exc.required_level,
                },
            },
        )

    @app.exception_handler(EducationError)
    async def _handle_edu_error(_request: Request, exc: EducationError) -> JSONResponse:
        payload: dict = {"error": {"code": exc.code, "message": exc.message}}
        if exc.extra:
            payload["error"].update(exc.extra)
        return JSONResponse(status_code=exc.status_code, content=payload)
