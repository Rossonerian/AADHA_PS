"""Verifier background job stubs (owned by Arnav)."""

from typing import Any

from sqlalchemy.orm import Session


def score_open_claims(db: Session | None = None) -> dict[str, Any]:
    """Stub for daily open-claim scoring job."""
    del db
    return {"status": "stub", "scored": 0}
