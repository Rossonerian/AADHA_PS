"""Service helpers for JWT claim extraction, profile upsert, and onboarding state."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models import UserRecord
from app.profiles.models import UserProfileRecord
from app.profiles.schemas import (
    MAX_AVATAR_URL_LENGTH,
    MAX_DISPLAY_NAME_LENGTH,
    ProfileUpdateRequest,
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _clean_avatar_url(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned or len(cleaned) > MAX_AVATAR_URL_LENGTH:
        return None
    parsed = urlsplit(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return cleaned


def extract_avatar_url(claims: dict[str, Any]) -> str | None:
    """Extract a validated http(s) avatar URL from top-level or nested JWT claims."""
    for key in ("picture", "image", "avatar_url"):
        found = _clean_avatar_url(claims.get(key))
        if found is not None:
            return found

    user_metadata = claims.get("user_metadata")
    if isinstance(user_metadata, dict):
        for key in ("avatar_url", "picture", "image"):
            found = _clean_avatar_url(user_metadata.get(key))
            if found is not None:
                return found

    return None


def extract_display_name(
    claims: dict[str, Any],
    fallback_name: str | None = None,
) -> str:
    """Extract a clean display name from JWT claims, fallback user name, or email."""
    user_metadata = claims.get("user_metadata")
    if isinstance(user_metadata, dict):
        for key in ("full_name", "name"):
            value = user_metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:MAX_DISPLAY_NAME_LENGTH]

    claim_name = claims.get("name")
    if isinstance(claim_name, str) and claim_name.strip():
        return claim_name.strip()[:MAX_DISPLAY_NAME_LENGTH]

    if isinstance(fallback_name, str) and fallback_name.strip():
        return fallback_name.strip()[:MAX_DISPLAY_NAME_LENGTH]

    email = claims.get("email")
    if isinstance(email, str) and email.strip():
        local_part = email.strip().split("@", 1)[0].strip()
        if local_part:
            return local_part[:MAX_DISPLAY_NAME_LENGTH]
        return email.strip()[:MAX_DISPLAY_NAME_LENGTH]

    return ""


def upsert_profile_from_claims(
    db: Session,
    user_id: str,
    claims: dict[str, Any],
    fallback_name: str | None = None,
) -> UserProfileRecord:
    """Idempotently create or backfill a `user_profiles` row from verified JWT claims."""
    claim_name = extract_display_name(claims, fallback_name=fallback_name)
    claim_avatar = extract_avatar_url(claims)

    existing = db.get(UserProfileRecord, user_id)
    if existing is None:
        now = _utcnow()
        record = UserProfileRecord(
            user_id=user_id,
            display_name=claim_name,
            avatar_url=claim_avatar,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        try:
            db.commit()
            db.refresh(record)
            return record
        except IntegrityError:
            db.rollback()
            existing = db.get(UserProfileRecord, user_id)
            if existing is None:
                raise

    changed = False
    if not existing.display_name.strip() and claim_name:
        existing.display_name = claim_name
        changed = True
    if not existing.avatar_url and claim_avatar:
        existing.avatar_url = claim_avatar
        changed = True

    if changed:
        existing.updated_at = _utcnow()
        db.commit()
        db.refresh(existing)

    return existing


def get_or_create_profile(
    db: Session,
    user_id: str,
    fallback_name: str = "",
) -> UserProfileRecord:
    """Fetch `user_profiles` row for `user_id`, provisioning one if absent."""
    existing = db.get(UserProfileRecord, user_id)
    if existing is not None:
        return existing
    user_row = db.get(UserRecord, user_id)
    resolved_name = (
        fallback_name.strip() or (user_row.name.strip() if user_row else "")
    )[:MAX_DISPLAY_NAME_LENGTH]
    return upsert_profile_from_claims(db, user_id, {}, fallback_name=resolved_name)


def update_profile(
    db: Session,
    user_id: str,
    payload: ProfileUpdateRequest,
) -> UserProfileRecord:
    """Apply validated partial updates to `user_profiles` and sync `users.name`."""
    record = get_or_create_profile(db, user_id)
    fields = payload.model_fields_set

    if "display_name" in fields and payload.display_name is not None:
        record.display_name = payload.display_name
        user_row = db.get(UserRecord, user_id)
        if user_row is not None:
            user_row.name = payload.display_name
    if "avatar_url" in fields:
        record.avatar_url = payload.avatar_url
    if "goal" in fields:
        record.goal = payload.goal
    if "experience" in fields:
        record.experience = payload.experience
    if "weekly_minutes" in fields:
        record.weekly_minutes = payload.weekly_minutes

    if fields:
        record.updated_at = _utcnow()
        db.commit()
        db.refresh(record)

    return record


def complete_onboarding(db: Session, user_id: str) -> UserProfileRecord:
    """Idempotently mark first-run profile onboarding as completed."""
    record = get_or_create_profile(db, user_id)
    if record.onboarding_completed_at is None:
        now = _utcnow()
        record.onboarding_completed_at = now
        record.updated_at = now
        db.commit()
        db.refresh(record)
    return record
