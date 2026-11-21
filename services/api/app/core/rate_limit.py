"""Per-user and per-IP sliding-window rate limiting and request body size caps."""

from __future__ import annotations

import ipaddress
import json
import math
import re
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.errors import AppError

_SCOPE_KEY = "paisaproof.rate_limit"

_EXEMPT_PATHS = frozenset({"/api/v1/health", "/api/v1/me"})
_EXACT_PROTECTED_ROUTES = frozenset(
    {
        ("POST", "/api/v1/verify"),
        ("POST", "/api/v1/nasdaq-verifier/submit"),
        ("GET", "/api/v1/nasdaq-verifier/challenge"),
        ("GET", "/api/v1/explain"),
        ("POST", "/api/v1/onboarding/answer"),
        ("POST", "/api/v1/study/start"),
        ("PATCH", "/api/v1/me/profile"),
    }
)
_ASSESSMENT_RE = re.compile(r"^/api/v1/assessments/[^/]+/(submit|start)$")
_LESSON_CHECK_RE = re.compile(r"^/api/v1/lessons/[^/]+/check$")
_SOURCE_RE = re.compile(r"^/api/v1/sources/[^/]+$")
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
    """Thread-safe in-memory sliding-window limiter with a bounded bucket table.

    Keys are only ever a client IP (derived from trusted proxy config) or a user id taken
    from a *verified* token, so callers cannot mint unlimited keys. As defence in depth the
    table is capped: idle buckets are swept first, then the least recently used is evicted.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        max_buckets: int = 50_000,
    ) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: OrderedDict[str, deque[float]] = OrderedDict()
        self._max_buckets = max(1, int(max_buckets))
        self._last_sweep = clock()

    def reset(self) -> None:
        """Clear all recorded rate-limit timestamps."""
        with self._lock:
            self._buckets.clear()

    def bucket_count(self) -> int:
        """Return the number of tracked buckets (for tests and diagnostics)."""
        with self._lock:
            return len(self._buckets)

    def set_max_buckets(self, max_buckets: int) -> None:
        """Update the bucket cap."""
        with self._lock:
            self._max_buckets = max(1, int(max_buckets))

    def _sweep_idle(self, cutoff: float) -> None:
        idle = [k for k, b in self._buckets.items() if not b or b[-1] <= cutoff]
        for key in idle:
            del self._buckets[key]

    def _live_bucket(self, key: str, cutoff: float) -> deque[float] | None:
        bucket = self._buckets.get(key)
        if bucket is None:
            return None
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if not bucket:
            del self._buckets[key]
            return None
        return bucket

    def _record(self, key: str, now: float, cutoff: float) -> deque[float]:
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self._max_buckets:
                self._sweep_idle(cutoff)
            while len(self._buckets) >= self._max_buckets:
                self._buckets.popitem(last=False)
            bucket = deque()
            self._buckets[key] = bucket
        else:
            self._buckets.move_to_end(key)
        bucket.append(now)
        return bucket

    def consume(
        self, *, key: str, limit: int, window_seconds: int
    ) -> RateLimitDecision:
        """Record one hit for ``key`` unless it already used ``limit`` in the window."""
        scope = "user" if key.startswith("user:") else "ip"
        if limit <= 0:
            return RateLimitDecision(
                allowed=True, scope=scope, limit=limit, remaining=limit
            )
        window = max(1, int(window_seconds))
        now = self._clock()
        cutoff = now - window
        with self._lock:
            if now - self._last_sweep >= window:
                self._sweep_idle(cutoff)
                self._last_sweep = now
            bucket = self._live_bucket(key, cutoff)
            if bucket is not None and len(bucket) >= limit:
                retry_after = max(1, math.ceil(window - (now - bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    scope=scope,
                    limit=limit,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )
            bucket = self._record(key, now, cutoff)
            return RateLimitDecision(
                allowed=True,
                scope=scope,
                limit=limit,
                remaining=max(0, limit - len(bucket)),
            )


class RateLimitedError(AppError):
    """429 raised once a verified user exceeds the per-user window."""

    def __init__(self, decision: RateLimitDecision) -> None:
        super().__init__(
            code="RATE_LIMITED",
            message="Rate limit exceeded. Please retry shortly.",
            status_code=429,
            extra={
                "retry_after_seconds": decision.retry_after_seconds,
                "scope": decision.scope,
            },
        )
        self.headers = {
            "Retry-After": str(decision.retry_after_seconds),
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": "0",
        }


@dataclass
class RateLimitContext:
    """Per-request state shared between the middleware and the auth dependency."""

    window_seconds: int
    user_limit: int
    limit: int
    remaining: int
    user_checked: bool = False


_rate_limiter = SlidingWindowRateLimiter()


def enforce_user_rate_limit(scope: Scope, verified_user_id: str) -> None:
    """Apply the per-user window for a user whose token has already been verified.

    Called from the auth dependency, never with an unverified identity. No-op for routes
    the middleware did not mark as protected.
    """
    ctx = scope.get(_SCOPE_KEY)
    if not isinstance(ctx, RateLimitContext) or ctx.user_checked:
        return
    ctx.user_checked = True
    if ctx.user_limit <= 0:
        return
    decision = _rate_limiter.consume(
        key=f"user:{verified_user_id}",
        limit=ctx.user_limit,
        window_seconds=ctx.window_seconds,
    )
    if not decision.allowed:
        ctx.limit, ctx.remaining = decision.limit, 0
        raise RateLimitedError(decision)
    ctx.limit = decision.limit
    ctx.remaining = min(ctx.remaining, decision.remaining)


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Return the shared process-wide rate limiter."""
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the shared process-wide rate limiter (intended for test isolation)."""
    _rate_limiter.reset()


def _get_header(scope: Scope, target_name: bytes) -> str | None:
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name.lower() == target_name:
            return str(bytes(raw_value).decode("latin-1"))
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
    if upper_method == "GET":
        return bool(_SOURCE_RE.match(path))
    return bool(
        upper_method == "POST"
        and (
            _ASSESSMENT_RE.match(path)
            or _STUDY_SUBMIT_RE.match(path)
            or _SCENARIO_ANSWER_RE.match(path)
            or _LESSON_CHECK_RE.match(path)
        )
    )


def _normalize_ip(raw: str) -> str | None:
    try:
        return str(ipaddress.ip_address(raw.strip()))
    except ValueError:
        return None


def _extract_client_ip(scope: Scope, trusted_proxy_hops: int = 0) -> str:
    """Return the client IP; X-Forwarded-For is honoured only behind trusted proxies.

    With ``trusted_proxy_hops = N`` the Nth address from the right of the header is used
    (the one appended by the outermost trusted proxy); anything further left is
    client-controlled and ignored. With 0 (default) the socket peer is always used.
    """
    if trusted_proxy_hops > 0:
        forwarded = _get_header(scope, b"x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if len(hops) >= trusted_proxy_hops:
                candidate = _normalize_ip(hops[-trusted_proxy_hops])
                if candidate:
                    return candidate
    client = scope.get("client")
    if isinstance(client, (tuple, list)) and client and isinstance(client[0], str):
        host = client[0].strip()
        if host:
            return host
    return "unknown"


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

        ip_key = _extract_client_ip(scope, current_settings.trusted_proxy_hops)
        limiter = get_rate_limiter()
        limiter.set_max_buckets(current_settings.rate_limit_max_buckets)
        decision = limiter.consume(
            key=f"ip:{ip_key}",
            limit=current_settings.rate_limit_ip_per_window,
            window_seconds=current_settings.rate_limit_window_seconds,
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

        # The per-user window is applied later, in the auth dependency, keyed by the
        # verified subject; unauthenticated callers only ever consume their IP bucket.
        ctx = RateLimitContext(
            window_seconds=current_settings.rate_limit_window_seconds,
            user_limit=current_settings.rate_limit_user_per_window,
            limit=max(1, decision.limit),
            remaining=decision.remaining,
        )
        scope[_SCOPE_KEY] = ctx

        async def send_with_rate_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-RateLimit-Limit"] = str(ctx.limit)
                headers["X-RateLimit-Remaining"] = str(ctx.remaining)
            await send(message)

        await self.app(scope, receive, send_with_rate_headers)
