"""Public package surface for PaisaProof Education module.

Hardhik's app/main.py and GET /me can import directly:
    from app.education import (
        router as education_router, register_exception_handlers, get_user_unlocks,
    )
"""

from .exceptions import ToolLockedError, register_exception_handlers
from .learning import ensure_level_unlocks, get_user_unlocks, require_tool_unlocked
from .loader import load_seed_directory, load_yaml_file
from .repository import EducationRepository, apply_migrations
from .router import router

__all__ = [
    "router",
    "register_exception_handlers",
    "ToolLockedError",
    "get_user_unlocks",
    "ensure_level_unlocks",
    "require_tool_unlocked",
    "load_seed_directory",
    "load_yaml_file",
    "EducationRepository",
    "apply_migrations",
]
