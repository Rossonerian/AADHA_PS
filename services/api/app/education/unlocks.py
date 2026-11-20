"""User tool-unlock lookup helper."""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.enums import LEVEL_UNLOCKS


def get_user_unlocks(db: Session, user_id: str, level: int) -> list[str]:
    """Return unlocked tool names for `user_id` from `unlocks` table or level defaults."""
    bind = db.get_bind()
    if inspect(bind).has_table("unlocks"):
        rows = db.execute(
            text(
                "SELECT tool FROM unlocks WHERE user_id = :user_id ORDER BY unlocked_at ASC"
            ),
            {"user_id": user_id},
        ).fetchall()
        if rows:
            return [str(row[0]) for row in rows]

    clamped_level = min(max(level, 1), 4)
    return [tool.value for tool in LEVEL_UNLOCKS[clamped_level]]
