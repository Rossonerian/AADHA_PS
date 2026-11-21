"""Tests for per-user / per-IP rate limiting, body size caps, and stale market warnings."""

from __future__ import annotations

import io
import json
import logging
import uuid
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.logging import get_logger
from app.main import create_app


def _make_client_with_env(
    monkeypatch: pytest.MonkeyPatch,
    **env_vars: str,
) -> TestClient:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return TestClient(create_app())


def test_per_user_rate_limit_returns_429_and_allows_second_user(
    migrated_db: str,
    make_jwt: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rate limiter blocks repeated requests per user with 429 + Retry-After."""
    del migrated_db
    with _make_client_with_env(
        monkeypatch,
        RATE_LIMIT_USER_PER_WINDOW="2",
        RATE_LIMIT_IP_PER_WINDOW="20",
        RATE_LIMIT_WINDOW_SECONDS="60",
    ) as limited_client:
        user1_token = make_jwt(str(uuid.uuid4()))
        user2_token = make_jwt(str(uuid.uuid4()))

        # Trigger protected routes (auth fails at dependency level or endpoint level,
        # after rate limit accounting consumes slots cleanly).
        for idx in range(2):
            resp = limited_client.post(
                "/api/v1/verify",
                headers={
                    "Authorization": f"Bearer {user1_token}",
                    "X-Forwarded-For": "198.51.100.10",
                },
                json={},
            )
            assert resp.status_code != 429
            assert resp.headers.get("X-RateLimit-Limit") == "2"
            assert resp.headers.get("X-RateLimit-Remaining") == str(1 - idx)

        blocked = limited_client.post(
            "/api/v1/verify",
            headers={
                "Authorization": f"Bearer {user1_token}",
                "X-Forwarded-For": "198.51.100.10",
            },
            json={},
        )
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) >= 1
        assert blocked.headers.get("X-RateLimit-Remaining") == "0"
        body = blocked.json()["error"]
        assert body["code"] == "RATE_LIMITED"
        assert body["scope"] == "user"
        assert body["retry_after_seconds"] >= 1

        # Protected GET route for same user is also blocked cleanly.
        blocked_explain = limited_client.get(
            "/api/v1/explain?symbol=TCS&year=2020",
            headers={
                "Authorization": f"Bearer {user1_token}",
                "X-Forwarded-For": "198.51.100.10",
            },
        )
        assert blocked_explain.status_code == 429
        assert blocked_explain.json()["error"]["scope"] == "user"

        # Protected Nasdaq challenge submit route for same user is also blocked cleanly.
        blocked_submit = limited_client.post(
            "/api/v1/nasdaq-verifier/submit",
            headers={
                "Authorization": f"Bearer {user1_token}",
                "X-Forwarded-For": "198.51.100.10",
            },
            json={"challenge_id": "x", "answers": []},
        )
        assert blocked_submit.status_code == 429
        assert blocked_submit.json()["error"]["scope"] == "user"

        # A distinct user on a separate IP is not blocked.
        other_user_resp = limited_client.post(
            "/api/v1/verify",
            headers={
                "Authorization": f"Bearer {user2_token}",
                "X-Forwarded-For": "198.51.100.11",
            },
            json={},
        )
        assert other_user_resp.status_code != 429

    get_settings.cache_clear()


def test_per_ip_rate_limit_blocks_distinct_users_sharing_ip(
    migrated_db: str,
    make_jwt: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rate limiter enforces per-IP limits even across multiple user identities."""
    del migrated_db
    with _make_client_with_env(
        monkeypatch,
        RATE_LIMIT_USER_PER_WINDOW="20",
        RATE_LIMIT_IP_PER_WINDOW="3",
        RATE_LIMIT_WINDOW_SECONDS="60",
    ) as limited_client:
        shared_ip = "203.0.113.42"
        for _ in range(3):
            token = make_jwt(str(uuid.uuid4()))
            ok_resp = limited_client.get(
                "/api/v1/explain?symbol=TCS&year=2020",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Forwarded-For": shared_ip,
                },
            )
            assert ok_resp.status_code != 429

        blocked = limited_client.post(
            "/api/v1/verify",
            headers={
                "Authorization": f"Bearer {make_jwt(str(uuid.uuid4()))}",
                "X-Forwarded-For": f"{shared_ip}, 10.0.0.1",
            },
            json={},
        )
        assert blocked.status_code == 429
        err = blocked.json()["error"]
        assert err["code"] == "RATE_LIMITED"
        assert err["scope"] == "ip"
        assert int(blocked.headers["Retry-After"]) >= 1

    get_settings.cache_clear()


def test_request_body_size_cap_returns_413_standard_and_streamed(
    migrated_db: str,
    make_jwt: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Oversized request bodies return 413 PAYLOAD_TOO_LARGE; /verify has separate cap."""
    del migrated_db
    with _make_client_with_env(
        monkeypatch,
        MAX_REQUEST_BODY_BYTES="200",
        MAX_VERIFY_BODY_BYTES="500",
    ) as capped_client:
        token = make_jwt(str(uuid.uuid4()))

        # Exceeds default 200-byte cap on non-verify route (via Content-Length).
        oversized_general = capped_client.post(
            "/api/v1/onboarding/answer",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            content=json.dumps({"padding": "x" * 300}).encode("utf-8"),
        )
        assert oversized_general.status_code == 413
        assert oversized_general.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert oversized_general.json()["error"]["max_bytes"] == 200

        # Chunked / streamed body without Content-Length also hits 413 PAYLOAD_TOO_LARGE.
        def _stream_chunks() -> Generator[bytes, None, None]:
            yield b'{"padding":"'
            yield b"a" * 250
            yield b'"}'

        oversized_streamed = capped_client.post(
            "/api/v1/onboarding/answer",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            content=_stream_chunks(),
        )
        assert oversized_streamed.status_code == 413
        assert oversized_streamed.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

        # A 300-byte payload passes /verify (under 500 cap) and stops at validation/service layer.
        within_verify = capped_client.post(
            "/api/v1/verify",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            content=json.dumps({"padding": "x" * 300}).encode("utf-8"),
        )
        assert within_verify.status_code != 413

        # Over 500 bytes on /verify hits 413 with max_bytes=500.
        oversized_verify = capped_client.post(
            "/api/v1/verify",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            content=json.dumps({"text": "x" * 600}).encode("utf-8"),
        )
        assert oversized_verify.status_code == 413
        assert oversized_verify.json()["error"]["max_bytes"] == 500

    get_settings.cache_clear()


def test_health_exempt_from_rate_limit_and_logs_stale_warning(
    migrated_db: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """/api/v1/health stays exempt from rate limits and warns when market data is stale."""
    del migrated_db
    monkeypatch.setattr("app.main.get_market_data_as_of", lambda: "2020-01-01")
    with _make_client_with_env(
        monkeypatch,
        RATE_LIMIT_USER_PER_WINDOW="1",
        RATE_LIMIT_IP_PER_WINDOW="1",
        MARKET_DATA_MAX_STALE_DAYS="5",
    ) as health_client:
        main_logger = get_logger("paisaproof.main")
        stream_handler = next(
            h for h in main_logger.handlers if isinstance(h, logging.StreamHandler)
        )
        log_buf = io.StringIO()
        prev_stream = stream_handler.setStream(log_buf)
        try:
            for _ in range(4):
                resp = health_client.get("/api/v1/health")
                assert resp.status_code == 200
                assert resp.json()["market_data_as_of"] == "2020-01-01"
        finally:
            stream_handler.setStream(prev_stream)

        lines = [json.loads(line) for line in log_buf.getvalue().splitlines() if line]
        stale_logs = [
            entry for entry in lines if entry["message"] == "market_data_stale"
        ]
        assert stale_logs
        assert stale_logs[-1]["level"] == "WARNING"
        assert stale_logs[-1]["extra"]["market_data_as_of"] == "2020-01-01"

    get_settings.cache_clear()
