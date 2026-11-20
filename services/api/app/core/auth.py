"""Supabase JWT verification, auto-provisioning, and level-gating dependencies."""

import uuid
from collections.abc import Callable
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import ToolLockedError, UnauthorizedError
from app.core.models import UserRecord

security = HTTPBearer(auto_error=False)


class User(BaseModel):
    """Authenticated user identity and current platform level."""

    id: str
    level: int
    name: str = ""
    email: str | None = None


@lru_cache(maxsize=4)
def _get_jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Validate a Supabase HS256, RS256, or ES256 JWT and return its decoded claims."""
    if not token or not token.strip():
        raise UnauthorizedError("Missing authentication token")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid authentication token") from exc

    alg = header.get("alg")
    current_settings = get_settings()

    if alg == "HS256":
        secret = current_settings.supabase_jwt_secret
        if not secret:
            raise UnauthorizedError("JWT verification secret is not configured")
        try:
            claims = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("Authentication token has expired") from exc
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid authentication token") from exc
    elif alg in {"RS256", "ES256"}:
        if not current_settings.supabase_url:
            raise UnauthorizedError(
                "Supabase URL is not configured for JWKS verification"
            )
        jwks_url = (
            f"{current_settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        )
        try:
            signing_key = _get_jwk_client(jwks_url).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("Authentication token has expired") from exc
        except Exception as exc:
            raise UnauthorizedError("Invalid authentication token") from exc
    else:
        raise UnauthorizedError("Unsupported authentication token algorithm")

    sub = claims.get("sub")
    if not isinstance(sub, str):
        raise UnauthorizedError("Authentication token missing subject")

    try:
        normalized_sub = str(uuid.UUID(sub))
    except ValueError as exc:
        raise UnauthorizedError(
            "Authentication token subject must be a valid UUID"
        ) from exc

    claims["sub"] = normalized_sub
    return dict(claims)


def _extract_user_name(claims: dict[str, Any]) -> str:
    user_metadata = claims.get("user_metadata")
    if isinstance(user_metadata, dict):
        for key in ("full_name", "name"):
            value = user_metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:255]

    for key in ("name", "email"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]

    return ""


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency returning the authenticated user, auto-provisioning on first login."""
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise UnauthorizedError("Authentication credentials were not provided")

    claims = verify_supabase_jwt(credentials.credentials)
    user_id = claims["sub"]
    email_raw = claims.get("email")
    email = email_raw if isinstance(email_raw, str) else None

    record = db.get(UserRecord, user_id)
    if record is None:
        record = UserRecord(
            id=user_id,
            name=_extract_user_name(claims),
            current_level=1,
        )
        db.add(record)
        try:
            db.commit()
            db.refresh(record)
        except IntegrityError:
            db.rollback()
            record = db.get(UserRecord, user_id)
            if record is None:
                raise UnauthorizedError("Failed to provision user account") from None

    return User(
        id=record.id,
        level=record.current_level,
        name=record.name,
        email=email,
    )


def require_level(min_level: int) -> Callable[[User], User]:
    """Dependency factory enforcing that `current_user.level >= min_level`."""

    def _check_level(user: User = Depends(current_user)) -> User:
        if user.level < min_level:
            raise ToolLockedError(required_level=min_level)
        return user

    return _check_level
