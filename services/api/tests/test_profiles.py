"""Tests for user profile claims upsert, validation, onboarding completion, and migrations."""

import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.core.models import UserRecord
from app.profiles.models import UserProfileRecord
from app.profiles.service import extract_avatar_url, upsert_profile_from_claims
from tests.conftest import ALEMBIC_INI_PATH, REPO_ROOT


def _make_custom_jwt(
    secret: str,
    *,
    sub: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def test_profile_routes_require_authentication(client: TestClient) -> None:
    """Profile update and onboarding completion endpoints require bearer auth."""
    patch_resp = client.patch("/api/v1/me/profile", json={"display_name": "Riya"})
    assert patch_resp.status_code == 401
    assert patch_resp.json()["error"]["code"] == "UNAUTHORIZED"

    complete_resp = client.post("/api/v1/me/onboarding/complete")
    assert complete_resp.status_code == 401
    assert complete_resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_first_login_upserts_user_and_profile_from_google_claims(
    client: TestClient,
    db_session: Session,
    jwt_secret: str,
) -> None:
    """First authenticated call prefills display_name and Google picture into user_profiles."""
    user_id = str(uuid.uuid4())
    avatar = "https://lh3.googleusercontent.com/a/test-avatar=s96-c"
    token = _make_custom_jwt(
        jwt_secret,
        sub=user_id,
        extra_claims={
            "name": "Ananya Verma",
            "email": "ananya@example.com",
            "picture": avatar,
        },
    )

    resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == user_id
    assert body["name"] == "Ananya Verma"
    assert body["onboarding_completed"] is False
    assert body["data_origin"] == "real"
    assert body["profile"]["user_id"] == user_id
    assert body["profile"]["display_name"] == "Ananya Verma"
    assert body["profile"]["avatar_url"] == avatar
    assert body["profile"]["goal"] is None
    assert body["profile"]["experience"] is None
    assert body["profile"]["weekly_minutes"] is None
    assert body["profile"]["onboarding_completed_at"] is None

    db_session.expire_all()
    user_row = db_session.get(UserRecord, user_id)
    profile_row = db_session.get(UserProfileRecord, user_id)
    assert user_row is not None
    assert profile_row is not None
    assert profile_row.display_name == "Ananya Verma"
    assert profile_row.avatar_url == avatar


def test_claims_upsert_is_idempotent_and_preserves_user_edits(
    client: TestClient,
    db_session: Session,
    jwt_secret: str,
) -> None:
    """Repeated logins do not duplicate rows and never clobber user-edited fields."""
    user_id = str(uuid.uuid4())
    token_first = _make_custom_jwt(
        jwt_secret,
        sub=user_id,
        extra_claims={
            "name": "Claim One",
            "email": "maya@example.com",
            "picture": "https://example.com/avatar1.png",
        },
    )
    first_resp = client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {token_first}"}
    )
    assert first_resp.status_code == 200

    edit_resp = client.patch(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token_first}"},
        json={
            "display_name": "Maya Custom",
            "avatar_url": "https://example.com/custom.png",
        },
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["profile"]["display_name"] == "Maya Custom"

    token_second = _make_custom_jwt(
        jwt_secret,
        sub=user_id,
        extra_claims={
            "name": "Different Google Name",
            "email": "maya@example.com",
            "picture": "https://example.com/avatar2.png",
        },
    )
    second_resp = client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {token_second}"}
    )
    assert second_resp.status_code == 200
    assert second_resp.json()["name"] == "Maya Custom"
    assert second_resp.json()["profile"]["display_name"] == "Maya Custom"
    assert (
        second_resp.json()["profile"]["avatar_url"] == "https://example.com/custom.png"
    )

    rows = db_session.scalars(
        select(UserProfileRecord).where(UserProfileRecord.user_id == user_id)
    ).all()
    assert len(rows) == 1

    # Also test backfill when an existing profile has empty display_name / avatar_url
    rows[0].display_name = ""
    rows[0].avatar_url = None
    db_session.commit()
    backfilled = upsert_profile_from_claims(
        db_session,
        user_id,
        {"name": "Backfilled Name", "picture": "https://example.com/backfill.png"},
    )
    assert backfilled.display_name == "Backfilled Name"
    assert backfilled.avatar_url == "https://example.com/backfill.png"


def test_patch_profile_partial_updates_and_validation_errors(
    client: TestClient,
    db_session: Session,
    make_jwt: Callable[..., str],
) -> None:
    """PATCH /me/profile persists partial updates, syncs users.name, and enforces schema rules."""
    user_id = str(uuid.uuid4())
    token = make_jwt(
        user_id, email="dev@example.com", user_metadata={"full_name": "Dev"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    r1 = client.patch(
        "/api/v1/me/profile",
        headers=headers,
        json={"display_name": "  Maya Rao  "},
    )
    assert r1.status_code == 200
    assert r1.json()["profile"]["display_name"] == "Maya Rao"
    assert r1.json()["onboarding_completed"] is False
    assert r1.json()["data_origin"] == "real"

    r2 = client.patch(
        "/api/v1/me/profile",
        headers=headers,
        json={"goal": "avoid_scams", "experience": "some"},
    )
    assert r2.status_code == 200
    p2 = r2.json()["profile"]
    assert p2["display_name"] == "Maya Rao"
    assert p2["goal"] == "avoid_scams"
    assert p2["experience"] == "some"

    r3 = client.patch(
        "/api/v1/me/profile",
        headers=headers,
        json={"weekly_minutes": 20, "avatar_url": "https://example.com/a.png"},
    )
    assert r3.status_code == 200
    p3 = r3.json()["profile"]
    assert p3["weekly_minutes"] == 20
    assert p3["avatar_url"] == "https://example.com/a.png"

    # Explicit null clears nullable field
    r4 = client.patch(
        "/api/v1/me/profile",
        headers=headers,
        json={"avatar_url": None},
    )
    assert r4.status_code == 200
    assert r4.json()["profile"]["avatar_url"] is None

    db_session.expire_all()
    user_row = db_session.get(UserRecord, user_id)
    assert user_row is not None
    assert user_row.name == "Maya Rao"

    invalid_payloads: list[dict[str, Any]] = [
        {"goal": "get_rich_quick"},
        {"experience": "legendary"},
        {"weekly_minutes": 0},
        {"weekly_minutes": -10},
        {"weekly_minutes": 10081},
        {"weekly_minutes": True},
        {"display_name": "   "},
        {"display_name": None},
        {"display_name": "A" * 81},
        {"avatar_url": "javascript:alert(1)"},
        {"avatar_url": "not-a-url"},
        {"unknown_field": "nope"},
    ]
    for payload in invalid_payloads:
        bad = client.patch("/api/v1/me/profile", headers=headers, json=payload)
        assert (
            bad.status_code == 422
        ), f"Expected 422 for {payload}, got {bad.status_code}"
        err = bad.json()
        assert err["error"]["code"] == "VALIDATION_ERROR"
        assert isinstance(err["error"]["message"], str)


def test_complete_onboarding_is_idempotent(
    client: TestClient,
    make_jwt: Callable[..., str],
) -> None:
    """POST /me/onboarding/complete stamps onboarding_completed_at idempotently."""
    user_id = str(uuid.uuid4())
    token = make_jwt(user_id, email="newbie@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    me_before = client.get("/api/v1/me", headers=headers)
    assert me_before.status_code == 200
    assert me_before.json()["onboarding_completed"] is False

    first = client.post("/api/v1/me/onboarding/complete", headers=headers)
    assert first.status_code == 200
    body1 = first.json()
    assert body1["onboarding_completed"] is True
    assert body1["data_origin"] == "real"
    completed_at_1 = body1["profile"]["onboarding_completed_at"]
    assert completed_at_1 is not None

    second = client.post("/api/v1/me/onboarding/complete", headers=headers)
    assert second.status_code == 200
    assert second.json()["onboarding_completed"] is True
    assert second.json()["profile"]["onboarding_completed_at"] == completed_at_1

    me_after = client.get("/api/v1/me", headers=headers)
    assert me_after.status_code == 200
    assert me_after.json()["onboarding_completed"] is True
    assert me_after.json()["profile"]["onboarding_completed_at"] == completed_at_1


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"picture": "https://cdn.example.com/p.jpg"}, "https://cdn.example.com/p.jpg"),
        ({"picture": "javascript:alert(1)"}, None),
        ({"image": "http://cdn.example.com/p.png"}, "http://cdn.example.com/p.png"),
        (
            {"user_metadata": {"avatar_url": "https://cdn.example.com/meta.png"}},
            "https://cdn.example.com/meta.png",
        ),
        ({}, None),
    ],
)
def test_extract_avatar_url_sanitization(
    claims: dict[str, Any], expected: str | None
) -> None:
    """Only http(s) avatar URLs are extracted from claims."""
    assert extract_avatar_url(claims) == expected


def test_user_profiles_migration_downgrade_and_upgrade(migrated_db: str) -> None:
    """Alembic migration cleanly creates, drops, and recreates user_profiles."""
    del migrated_db
    inspector = inspect(get_engine())
    assert "user_profiles" in inspector.get_table_names()

    alembic_cfg = Config(str(ALEMBIC_INI_PATH))
    prev = os.getcwd()
    try:
        os.chdir(REPO_ROOT)
        command.downgrade(alembic_cfg, "20261121_submission_owner_fk")
        assert "user_profiles" not in inspect(get_engine()).get_table_names()
        command.upgrade(alembic_cfg, "head")
        assert "user_profiles" in inspect(get_engine()).get_table_names()
    finally:
        os.chdir(prev)
