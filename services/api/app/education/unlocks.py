"""User tool-unlock lookup helper for Hardhik's main.py /me route."""
from __future__ import annotations

from typing import Any, List

from .learning import get_user_unlocks as _get_user_unlocks
from .repository import EducationRepository


def get_user_unlocks(db: Any, user_id: str, level: int = 1) -> List[str]:
    """Adapter for Hardhik's GET /me endpoint accepting a db Session or Connection."""
    repo = EducationRepository(db)
    return _get_user_unlocks(repo, str(user_id), user_level=int(level))
