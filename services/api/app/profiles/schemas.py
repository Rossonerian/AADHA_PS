"""Pydantic request and response contracts for user profiles."""

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProfileGoal = Literal["learn_basics", "avoid_scams", "invest_smarter", "other"]
ProfileExperience = Literal["new", "some", "experienced"]
DataOrigin = Literal["real", "synthetic", "mixed"]

MAX_DISPLAY_NAME_LENGTH = 80
MAX_AVATAR_URL_LENGTH = 2048


def sanitize_http_url(value: str | None) -> str | None:
    """Validate and strip an http(s) URL; return None for blank/empty values."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_AVATAR_URL_LENGTH:
        raise ValueError(
            f"avatar_url must be at most {MAX_AVATAR_URL_LENGTH} characters"
        )
    parsed = urlsplit(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("avatar_url must be a valid http(s) URL")
    return cleaned


class UserProfileOut(BaseModel):
    """Serialized user profile record."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    display_name: str
    avatar_url: str | None = None
    goal: ProfileGoal | None = None
    experience: ProfileExperience | None = None
    weekly_minutes: int | None = None
    onboarding_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProfileUpdateRequest(BaseModel):
    """Validated payload for partial updates on `PATCH /api/v1/me/profile`."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    avatar_url: str | None = None
    goal: ProfileGoal | None = None
    experience: ProfileExperience | None = None
    weekly_minutes: int | None = Field(default=None, ge=1, le=10080)

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("display_name cannot be null")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name cannot be empty")
        if len(cleaned) > MAX_DISPLAY_NAME_LENGTH:
            raise ValueError(
                f"display_name must be at most {MAX_DISPLAY_NAME_LENGTH} characters"
            )
        return cleaned

    @field_validator("avatar_url")
    @classmethod
    def _validate_avatar_url(cls, value: str | None) -> str | None:
        return sanitize_http_url(value)

    @field_validator("weekly_minutes", mode="before")
    @classmethod
    def _reject_boolean_minutes(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("weekly_minutes must be an integer")
        return value


class ProfileResponse(BaseModel):
    """Unified envelope for profile mutations."""

    profile: UserProfileOut
    onboarding_completed: bool
    data_origin: DataOrigin = "real"
