"""Per-user and per-IP sliding-window rate limiting and request body size caps."""

from __future__ import annotations

import json
import math
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.errors import AppError

_EXEMPT_PATHS = frozenset({"/api/v1/health", "/api/v1/me"})
_EXACT_PROTECTED_ROUTES = frozenset(
    {
        ("POST", "/api/v1/verify"),
        ("POST", "/api/v1/nasdaq-verifier/submit"),
        ("GET", "/api/v1/nasdaq-verifier/challenge"),
        ("GET", "/api/v1/explain"),
        ("POST", "/api/v1/onboarding/answer"),
    }
)
_ASSESSMENT_SUBMIT_RE = re.compile(r"^/api/v1/assessments/[^/]+/submit$")
_STUDY_SUBMIT_RE = re.compile(r"^/api/v1/study/[^/]+/submit$")
_SCENARIO_ANSWER_RE = re.compile(r"^/api/v1/scenarios/[^/]+/answer$")


class PayloadTooLargeError(AppError):
    """Raised when a streamed request body exceeds the configured byte limit."""

    def __init__(self, max_bytes: int) -> None:
        super().__init__(
            code="PAYLOAD_TOO_LARGE",
            message="Request body exceeds maximum allowed size",
            status_code=413,
            extra={"max_bytes": max_bytes},
        )


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of evaluating sliding-window rate limits for a request."""

    allowed: bool
    scope: str
    limit: int
    remaining: int
    retry_after_seconds: int = 0


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter keyed by user and IP."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = {}

    def reset(self) -> None:
        """Clear all recorded rate-limit timestamps."""
        with self._lock:
            self._buckets.clear()

    def _prune(self, key: str, cutoff: float) -> deque[float]:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = deque()
            self._buckets[key] = bucket
            return bucket
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        return bucket

    def check_and_consume(
        self,
        *,
        user_key: str | None,
        ip_key: str,
        window_seconds: int,
        user_limit: int,
        ip_limit: int,
    ) -> RateLimitDecision:
        """Evaluate user and IP limits and record the request if allowed."""
        window = max(1, int(window_seconds))
        now = self._clock()
        cutoff = now - window

        with self._lock:
            user_bucket = (
                self._prune(user_key, cutoff) if user_key and user_limit > 0 else None
            )
            if (
                user_bucket is not None
                and user_limit > 0
                and len(user_bucket) >= user_limit
            ):
                retry_after = max(1, math.ceil(window - (now - user_bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    scope="user",
                    limit=user_limit,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            ip_bucket = self._prune(f"ip:{ip_key}", cutoff) if ip_limit > 0 else None
            if ip_bucket is not None and ip_limit > 0 and len(ip_bucket) >= ip_limit:
                retry_after = max(1, math.ceil(window - (now - ip_bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    scope="ip",
                    limit=ip_limit,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            if user_bucket is not None:
                user_bucket.append(now)
            if ip_bucket is not None:
                ip_bucket.append(now)

            if user_bucket is not None and user_limit > 0:
                user_rem = max(0, user_limit - len(user_bucket))
                ip_rem = (
                    max(0, ip_limit - len(ip_bucket))
                    if ip_bucket is not None and ip_limit > 0
                    else user_rem
                )
                return RateLimitDecision(
                    allowed=True,
                    scope="user",
                    limit=user_limit,
                    remaining=min(user_rem, ip_rem),
                )

            effective_limit = max(1, ip_limit)
            ip_rem = (
                max(0, ip_limit - len(ip_bucket))
                if ip_bucket is not None and ip_limit > 0
                else effective_limit
            )
            return RateLimitDecision(
                allowed=True,
                scope="ip",
                limit=effective_limit,
                remaining=ip_rem,
            )


_rate_limiter = SlidingWindowRateLimiter()


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Return the shared process-wide rate limiter."""
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the shared process-wide rate limiter (intended for test isolation)."""
    _rate_limiter.reset()


def _get_header(scope: Scope, target_name: bytes) -> str | None:
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name.lower() == target_name:
            return raw_value.decode("latin-1")
    return None


def _normalize_path(scope: Scope) -> str:
    raw = str(scope.get("path", "/"))
    stripped = raw.rstrip("/")
    return stripped or "/"


def _is_protected_route(method: str, path: str) -> bool:
    upper_method = method.upper()
    if upper_method == "OPTIONS" or path in _EXEMPT_PATHS:
        return False
    if (upper_method, path) in _EXACT_PROTECTED_ROUTES:
        return True
    return bool(
        upper_method == "POST"
        and (
            _ASSESSMENT_SUBMIT_RE.match(path)
            or _STUDY_SUBMIT_RE.match(path)
            or _SCENARIO_ANSWER_RE.match(path)
        )
    )


def _extract_client_ip(scope: Scope) -> str:
    forwarded = _get_header(scope, b"x-forwarded-for")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    client = scope.get("client")
    if isinstance(client, (tuple, list)) and client and isinstance(client[0], str):
        host = client[0].strip()
        if host:
            return host
    return "unknown"


def _extract_bearer_sub(scope: Scope) -> str | None:
    auth_header = _get_header(scope, b"authorization")
    if not auth_header:
        return None
    parts = auth_header.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
    if not isinstance(claims, dict):
        return None
    sub = claims.get("sub")
    if isinstance(sub, str) and sub.strip():
        return f"user:{sub.strip()}"
    return None


async def _send_json_error(
    send: Send,
    *,
    status_code: int,
    code: str,
    message: str,
    extra: dict[str, Any] | None = None,
    headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    error_body: dict[str, Any] = {"code": code, "message": message}
    if extra:
        error_body.update(extra)
    payload = json.dumps({"error": error_body}, separators=(",", ":")).encode("utf-8")
    response_headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(payload)).encode("ascii")),
    ]
    if headers:
        response_headers.extend(headers)
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": response_headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": payload,
            "more_body": False,
        }
    )


class RequestSizeLimitMiddleware:
    """ASGI middleware enforcing per-route request payload byte limits."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = _normalize_path(scope)
        current_settings = get_settings()
        limit = (
            current_settings.max_verify_body_bytes
            if path == "/api/v1/verify"
            else current_settings.max_request_body_bytes
        )
        if limit <= 0:
            await self.app(scope, receive, send)
            return

        content_length_raw = _get_header(scope, b"content-length")
        if content_length_raw is not None:
            try:
                content_length = int(content_length_raw)
            except ValueError:
                content_length = 0
            if content_length > limit:
                await _send_json_error(
                    send,
                    status_code=413,
                    code="PAYLOAD_TOO_LARGE",
                    message="Request body exceeds maximum allowed size",
                    extra={"max_bytes": limit},
                )
                return

        if content_length_raw is None and str(scope.get("method", "GET")).upper() in {
            "POST",
            "PUT",
            "PATCH",
        }:
            chunks: list[bytes] = []
            buffered_bytes = 0
            while True:
                message = await receive()
                msg_type = message.get("type")
                if msg_type == "http.disconnect":
                    break
                if msg_type == "http.request":
                    chunk = message.get("body", b"")
                    if isinstance(chunk, (bytes, bytearray)):
                        buffered_bytes += len(chunk)
                        if buffered_bytes > limit:
                            await _send_json_error(
                                send,
                                status_code=413,
                                code="PAYLOAD_TOO_LARGE",
                                message="Request body exceeds maximum allowed size",
                                extra={"max_bytes": limit},
                            )
                            return
                        if chunk:
                            chunks.append(bytes(chunk))
                    if not message.get("more_body", False):
                        break

            buffered_body = b"".join(chunks)
            body_sent = False

            async def replay_receive() -> Message:
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {
                        "type": "http.request",
                        "body": buffered_body,
                        "more_body": False,
                    }
                return await receive()

            await self.app(scope, replay_receive, send)
            return

        received_bytes = 0
        response_started = False

        async def checked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def checked_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                chunk = message.get("body", b"")
                if isinstance(chunk, (bytes, bytearray)):
                    received_bytes += len(chunk)
                    if received_bytes > limit:
                        raise PayloadTooLargeError(limit)
            return message

        try:
            await self.app(scope, checked_receive, checked_send)
        except PayloadTooLargeError:
            if not response_started:
                await _send_json_error(
                    send,
                    status_code=413,
                    code="PAYLOAD_TOO_LARGE",
                    message="Request body exceeds maximum allowed size",
                    extra={"max_bytes": limit},
                )
            return


class RateLimitMiddleware:
    """ASGI middleware enforcing sliding-window per-user and per-IP rate limits."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        current_settings = get_settings()
        if not current_settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "GET"))
        path = _normalize_path(scope)
        if not _is_protected_route(method, path):
            await self.app(scope, receive, send)
            return

        ip_key = _extract_client_ip(scope)
        user_key = _extract_bearer_sub(scope)
        decision = get_rate_limiter().check_and_consume(
            user_key=user_key,
            ip_key=ip_key,
            window_seconds=current_settings.rate_limit_window_seconds,
            user_limit=current_settings.rate_limit_user_per_window,
            ip_limit=current_settings.rate_limit_ip_per_window,
        )

        if not decision.allowed:
            await _send_json_error(
                send,
                status_code=429,
                code="RATE_LIMITED",
                message="Rate limit exceeded. Please retry shortly.",
                extra={
                    "retry_after_seconds": decision.retry_after_seconds,
                    "scope": decision.scope,
                },
                headers=[
                    (
                        b"retry-after",
                        str(decision.retry_after_seconds).encode("ascii"),
                    ),
                    (b"x-ratelimit-limit", str(decision.limit).encode("ascii")),
                    (b"x-ratelimit-remaining", b"0"),
                ],
            )
            return

        async def send_with_rate_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-RateLimit-Limit"] = str(decision.limit)
                headers["X-RateLimit-Remaining"] = str(decision.remaining)
            await send(message)

        await self.app(scope, receive, send_with_rate_headers)
