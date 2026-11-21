"""Tests for Neon Auth EdDSA & Supabase JWT verification, `/api/v1/me`, and level gating."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Annotated, Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import (
    User,
    _get_jwk_client,
    require_level,
    verify_jwt,
    verify_supabase_jwt,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import UnauthorizedError, register_exception_handlers
from app.core.models import UserRecord


def test_me_missing_auth_header_returns_401(client: TestClient) -> None:
    """Missing Authorization header returns 401 UNAUTHORIZED."""
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert isinstance(body["error"]["message"], str)


def test_me_malformed_token_returns_401(client: TestClient) -> None:
    """Malformed bearer token returns 401 UNAUTHORIZED."""
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert isinstance(body["error"]["message"], str)


def test_me_expired_token_returns_401(
    client: TestClient,
    make_jwt: Callable[..., str],
) -> None:
    """Expired HS256 JWT returns 401 UNAUTHORIZED."""
    token = make_jwt(str(uuid.uuid4()), exp_delta_seconds=-120)
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_me_wrong_secret_returns_401(
    client: TestClient,
    make_jwt: Callable[..., str],
) -> None:
    """JWT signed with wrong secret returns 401 UNAUTHORIZED."""
    token = make_jwt(
        str(uuid.uuid4()), secret="wrong-secret-key-not-matching-server-32b"
    )
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_me_non_uuid_subject_returns_401(
    client: TestClient,
    make_jwt: Callable[..., str],
) -> None:
    """JWT with a non-UUID `sub` claim returns 401 UNAUTHORIZED."""
    token = make_jwt("user-123")
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_me_auto_provisions_level_1_user(
    client: TestClient,
    db_session: Session,
    make_jwt: Callable[..., str],
) -> None:
    """First login with valid HS256 JWT auto-creates a level 1 user row and returns unlocks."""
    user_id = str(uuid.uuid4())
    token = make_jwt(
        user_id,
        email="riya@example.com",
        user_metadata={"full_name": "Riya Sharma"},
    )

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user_id
    assert body["name"] == "Riya Sharma"
    assert body["level"] == 1
    assert body["unlocks"] == ["scenarios", "red_flag_check"]
    assert body["onboarding_completed"] is False
    assert body["data_origin"] == "real"
    assert body["profile"]["user_id"] == user_id
    assert body["profile"]["display_name"] == "Riya Sharma"

    db_session.expire_all()
    record = db_session.get(UserRecord, user_id)
    assert record is not None
    assert record.current_level == 1
    assert record.name == "Riya Sharma"

    repeat_response = client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert repeat_response.status_code == 200
    assert repeat_response.json()["id"] == user_id


def test_me_existing_level_3_user_returns_level_3_unlocks(
    client: TestClient,
    db_session: Session,
    make_jwt: Callable[..., str],
) -> None:
    """Existing user at level 3 receives level 3 and cumulative unlocks including verifier."""
    user_id = str(uuid.uuid4())
    db_session.add(UserRecord(id=user_id, name="Arjun Mehta", current_level=3))
    db_session.commit()

    token = make_jwt(user_id)
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user_id
    assert body["name"] == "Arjun Mehta"
    assert body["level"] == 3
    assert body["unlocks"] == [
        "scenarios",
        "red_flag_check",
        "explain_stock",
        "verifier",
    ]
    assert body["onboarding_completed"] is False
    assert body["data_origin"] == "real"
    assert body["profile"]["display_name"] == "Arjun Mehta"


def test_require_level_blocks_lower_level_with_403_tool_locked(
    migrated_db: str,
    db_session: Session,
    make_jwt: Callable[..., str],
) -> None:
    """`require_level(3)` raises 403 TOOL_LOCKED with required_level for level 1 users."""
    del migrated_db
    gated_app = FastAPI()
    register_exception_handlers(gated_app)
    gated_app.dependency_overrides[get_db] = lambda: db_session

    @gated_app.get("/gated")
    def _gated_endpoint(
        user: Annotated[User, Depends(require_level(3))],
    ) -> dict[str, int]:
        return {"level": user.level}

    low_user_id = str(uuid.uuid4())
    high_user_id = str(uuid.uuid4())
    db_session.add(UserRecord(id=low_user_id, name="Beginner", current_level=1))
    db_session.add(UserRecord(id=high_user_id, name="Verifier", current_level=3))
    db_session.commit()

    with TestClient(gated_app) as test_client:
        denied = test_client.get(
            "/gated",
            headers={"Authorization": f"Bearer {make_jwt(low_user_id)}"},
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "TOOL_LOCKED"
        assert denied.json()["error"]["required_level"] == 3

        allowed = test_client.get(
            "/gated",
            headers={"Authorization": f"Bearer {make_jwt(high_user_id)}"},
        )
        assert allowed.status_code == 200
        assert allowed.json() == {"level": 3}


def test_verify_supabase_jwt_alias_preserved() -> None:
    """`verify_supabase_jwt` remains an alias for `verify_jwt` for backward compatibility."""
    assert verify_supabase_jwt is verify_jwt


def test_me_neon_auth_eddsa_auto_provisions_level_1_user(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neon Auth EdDSA (Ed25519) JWT verifies via NEON_AUTH_JWKS_URL and provisions level 1."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    jwks_url = "https://ep-test.neonauth.us-east-2.aws.neon.tech/neondb/auth/.well-known/jwks.json"
    monkeypatch.setenv("NEON_AUTH_JWKS_URL", jwks_url)
    monkeypatch.setenv("NEON_AUTH_BASE_URL", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    get_settings.cache_clear()
    _get_jwk_client.cache_clear()

    requested_urls: list[str] = []

    class _FakePyJWKClient:
        def __init__(self, url: str) -> None:
            requested_urls.append(url)

        def get_signing_key_from_jwt(self, token: str) -> Any:
            del token
            return SimpleNamespace(key=public_key)

    monkeypatch.setattr("app.core.auth.PyJWKClient", _FakePyJWKClient)

    user_id = str(uuid.uuid4())
    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": user_id,
            "iss": "https://ep-test.neonauth.us-east-2.aws.neon.tech/neondb/auth",
            "name": "Kavya Iyer",
            "email": "kavya@example.com",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        private_key,
        algorithm="EdDSA",
        headers={"kid": "neon-ed25519-1"},
    )

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user_id
    assert body["name"] == "Kavya Iyer"
    assert body["level"] == 1
    assert body["unlocks"] == ["scenarios", "red_flag_check"]
    assert body["onboarding_completed"] is False
    assert body["data_origin"] == "real"
    assert body["profile"]["display_name"] == "Kavya Iyer"
    assert requested_urls == [jwks_url]

    db_session.expire_all()
    record = db_session.get(UserRecord, user_id)
    assert record is not None
    assert record.current_level == 1
    assert record.name == "Kavya Iyer"


def test_verify_jwt_neon_auth_issuer_routing_and_error_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EdDSA prefers Neon Auth JWKS by issuer, derives URL from base URL, and rejects bad tokens."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    wrong_key = ed25519.Ed25519PrivateKey.generate().public_key()

    neon_base = "https://ep-routing.neonauth.us-east-2.aws.neon.tech/neondb/auth"
    expected_neon_jwks = f"{neon_base}/.well-known/jwks.json"
    monkeypatch.setenv("NEON_AUTH_JWKS_URL", "")
    monkeypatch.setenv("NEON_AUTH_BASE_URL", neon_base)
    monkeypatch.setenv("SUPABASE_URL", "https://legacy.supabase.co")
    get_settings.cache_clear()
    _get_jwk_client.cache_clear()

    requested_urls: list[str] = []

    class _FakePyJWKClient:
        def __init__(self, url: str) -> None:
            self.url = url
            requested_urls.append(url)

        def get_signing_key_from_jwt(self, token: str) -> Any:
            del token
            if self.url == expected_neon_jwks:
                return SimpleNamespace(key=public_key)
            return SimpleNamespace(key=wrong_key)

    monkeypatch.setattr("app.core.auth.PyJWKClient", _FakePyJWKClient)

    user_id = str(uuid.uuid4())
    now = datetime.now(tz=UTC)
    valid_token = jwt.encode(
        {
            "sub": user_id,
            "iss": neon_base,
            "email": "dev@example.com",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        private_key,
        algorithm="EdDSA",
        headers={"kid": "neon-ed25519-2"},
    )
    claims = verify_jwt(valid_token)
    assert claims["sub"] == user_id
    assert requested_urls == [expected_neon_jwks]

    expired_token = jwt.encode(
        {
            "sub": user_id,
            "iss": neon_base,
            "iat": int((now - timedelta(minutes=30)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        private_key,
        algorithm="EdDSA",
        headers={"kid": "neon-ed25519-2"},
    )
    with pytest.raises(UnauthorizedError, match="expired"):
        verify_jwt(expired_token)

    wrong_sig_token = jwt.encode(
        {
            "sub": user_id,
            "iss": neon_base,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        ed25519.Ed25519PrivateKey.generate(),
        algorithm="EdDSA",
        headers={"kid": "neon-ed25519-2"},
    )
    with pytest.raises(UnauthorizedError, match="Invalid authentication token"):
        verify_jwt(wrong_sig_token)
