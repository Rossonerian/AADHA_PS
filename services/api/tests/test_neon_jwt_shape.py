"""verify_jwt against a Neon Auth shaped EdDSA token (iss is the web app origin via the proxy)."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.core.auth import _get_jwk_client, verify_jwt
from app.core.config import get_settings
from app.core.errors import UnauthorizedError

NEON_BASE = "https://ep-test.neonauth.c-3.ap-southeast-1.aws.neon.tech/neondb/auth"
WEB_ORIGIN = "https://paisaproof.vercel.app"


@pytest.fixture
def signer(monkeypatch: pytest.MonkeyPatch) -> ed25519.Ed25519PrivateKey:
    key = ed25519.Ed25519PrivateKey.generate()
    monkeypatch.setenv("NEON_AUTH_BASE_URL", NEON_BASE)
    monkeypatch.setenv("NEON_AUTH_JWKS_URL", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("CORS_ORIGINS", WEB_ORIGIN)
    get_settings.cache_clear()
    _get_jwk_client.cache_clear()

    class _Client:
        def __init__(self, url: str) -> None:
            del url

        def get_signing_key_from_jwt(self, token: str) -> Any:
            del token
            return SimpleNamespace(key=key.public_key())

    monkeypatch.setattr("app.core.auth.PyJWKClient", _Client)
    yield key
    get_settings.cache_clear()
    _get_jwk_client.cache_clear()


def _token(key: ed25519.Ed25519PrivateKey, **overrides: Any) -> str:
    now = datetime.now(tz=UTC)
    claims: dict[str, Any] = {
        "sub": str(uuid.uuid4()),
        "iss": WEB_ORIGIN,
        "aud": WEB_ORIGIN,
        "name": "Test User",
        "email": "t@example.com",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": "k1"})


@pytest.mark.parametrize(
    "iss",
    [
        WEB_ORIGIN,
        "https://ep-test.neonauth.c-3.ap-southeast-1.aws.neon.tech",
        NEON_BASE,
    ],
)
def test_neon_shaped_token_accepted_for_known_issuers(
    signer: ed25519.Ed25519PrivateKey, iss: str
) -> None:
    claims = verify_jwt(_token(signer, iss=iss))
    assert claims["email"] == "t@example.com"


def test_token_without_iss_accepted(signer: ed25519.Ed25519PrivateKey) -> None:
    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        signer,
        algorithm="EdDSA",
        headers={"kid": "k1"},
    )
    assert verify_jwt(token)["sub"]


def test_unknown_issuer_rejected(signer: ed25519.Ed25519PrivateKey) -> None:
    with pytest.raises(UnauthorizedError):
        verify_jwt(_token(signer, iss="https://evil.example.com"))


def test_extra_issuer_env_is_trusted(
    signer: ed25519.Ed25519PrivateKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEON_AUTH_EXTRA_ISSUERS", "https://other.example.com")
    get_settings.cache_clear()
    assert verify_jwt(_token(signer, iss="https://other.example.com"))["sub"]


def test_opaque_session_token_rejected(signer: ed25519.Ed25519PrivateKey) -> None:
    del signer
    with pytest.raises(UnauthorizedError):
        verify_jwt("Zk3vQ9opaqueSessionTokenWithoutDots")
