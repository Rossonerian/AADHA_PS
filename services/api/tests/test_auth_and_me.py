"""Tests for Supabase JWT authentication, auto-provisioning, `/api/v1/me`, and level gating."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import User, require_level
from app.core.db import get_db
from app.core.errors import register_exception_handlers
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
    assert response.json() == {
        "id": user_id,
        "name": "Riya Sharma",
        "level": 1,
        "unlocks": ["scenarios", "red_flag_check"],
    }

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
    assert response.json() == {
        "id": user_id,
        "name": "Arjun Mehta",
        "level": 3,
        "unlocks": ["scenarios", "red_flag_check", "explain_stock", "verifier"],
    }


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
