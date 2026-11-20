"""JWT verification (Neon Auth EdDSA JWKS and Supabase HS256), provisioning, and level gating."""

import uuid
from collections.abc import Callable
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.errors import ToolLockedError, UnauthorizedError
from app.core.models import UserRecord

security = HTTPBearer(auto_error=False)

_JWKS_ALGORITHMS = frozenset({"EdDSA", "RS256", "ES256"})


class User(BaseModel):
    """Authenticated user identity and current platform level."""

    id: str
    level: int
    name: str = ""
    email: str | None = None


@lru_cache(maxsize=4)
def _get_jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def _extract_origin(url: str) -> str:
    stripped = url.strip()
    if not stripped:
        return ""
    parts = urlsplit(stripped)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return ""


def _resolve_jwks_urls(token: str, current_settings: Settings) -> list[str]:
    """Resolve ordered JWKS URLs, preferring Neon Auth and routing by `iss` if both are set."""
    neon_jwks = current_settings.neon_auth_jwks_url.strip()
    neon_base = current_settings.neon_auth_base_url.strip().rstrip("/")
    if not neon_jwks and neon_base:
        neon_jwks = f"{neon_base}/.well-known/jwks.json"

    supabase_base = current_settings.supabase_url.strip().rstrip("/")
    supabase_jwks = (
        f"{supabase_base}/auth/v1/.well-known/jwks.json" if supabase_base else ""
    )

    candidates = list(dict.fromkeys(url for url in (neon_jwks, supabase_jwks) if url))
    if len(candidates) <= 1:
        return candidates

    try:
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        unverified_claims = {}

    iss = unverified_claims.get("iss") if isinstance(unverified_claims, dict) else None
    if isinstance(iss, str) and iss:
        neon_origin = _extract_origin(neon_base or neon_jwks)
        if neon_origin and iss.startswith(neon_origin):
            return [neon_jwks]
        supabase_origin = _extract_origin(supabase_base)
        if supabase_origin and iss.startswith(supabase_origin):
            return [supabase_jwks]

    return candidates


def verify_jwt(token: str) -> dict[str, Any]:
    """Validate a Neon Auth (EdDSA/JWKS) or Supabase (HS256/RS256/ES256) JWT."""
    if not token or not token.strip():
        raise UnauthorizedError("Missing authentication token")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid authentication token") from exc

    alg = header.get("alg")
    current_settings = get_settings()
    claims: dict[str, Any] | None = None

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
    elif isinstance(alg, str) and alg in _JWKS_ALGORITHMS:
        jwks_urls = _resolve_jwks_urls(token, current_settings)
        if not jwks_urls:
            raise UnauthorizedError("JWKS URL is not configured for JWT verification")
        last_exc: Exception | None = None
        for jwks_url in jwks_urls:
            try:
                signing_key = _get_jwk_client(jwks_url).get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[alg],
                    options={"verify_aud": False},
                )
                break
            except jwt.ExpiredSignatureError as exc:
                raise UnauthorizedError("Authentication token has expired") from exc
            except Exception as exc:
                last_exc = exc
        if claims is None:
            raise UnauthorizedError("Invalid authentication token") from last_exc
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


verify_supabase_jwt = verify_jwt


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

    claims = verify_jwt(credentials.credentials)
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
