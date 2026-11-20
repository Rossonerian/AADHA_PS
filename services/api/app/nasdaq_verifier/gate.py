"""Server-side unlock gate for `nasdaq_verifier`. Fails closed when data is missing."""

import json
import math
from dataclasses import dataclass
from typing import Any

from fastapi import Depends
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.auth import User, current_user
from app.core.db import get_db
from app.core.errors import ToolLockedError
from app.education.models import Plan, SkillScore

REQUIRED_LEVEL = 4
MAX_BRIER = 0.25
_COMPLETED = "completed"


@dataclass(frozen=True)
class GateInputs:
    """Learner progress facts the gate needs."""

    progress_pct: float | None
    brier: float | None


def read_gate_inputs(db: Session, user: User) -> GateInputs:
    """Read calculated plan completion and mean Brier from the Education tables.

    `plans.progress` is a map of lesson ID to status, not a stored percentage. Derive
    completion from the plan's lesson list and status map so the gate consumes progress
    written by actual lesson checks. Scalar percentages remain supported for older rows.
    """
    inspector = inspect(db.get_bind())
    progress: float | None = None
    brier: float | None = None
    if inspector.has_table("plans"):
        row = db.execute(
            select(Plan.lesson_ids, Plan.progress).where(Plan.user_id == user.id)
        ).fetchone()
        if row and row[1] is not None:
            lesson_ids = _decode_json(row[0])
            statuses = _decode_json(row[1])
            if isinstance(statuses, (int, float)):
                progress = float(statuses)
            elif isinstance(lesson_ids, list) and isinstance(statuses, dict):
                total = len(lesson_ids)
                if total:
                    completed = sum(
                        1
                        for lesson_id in lesson_ids
                        if statuses.get(lesson_id) == _COMPLETED
                    )
                    progress = round(100.0 * completed / total, 1)
    if inspector.has_table("skill_scores"):
        row = db.execute(
            select(func.avg(SkillScore.brier)).where(
                SkillScore.user_id == user.id, SkillScore.brier.is_not(None)
            )
        ).fetchone()
        if row and row[0] is not None:
            brier = float(row[0])
    return GateInputs(progress, brier)


def _decode_json(value: Any) -> Any:
    """Decode JSON values from raw SQL across SQLite and PostgreSQL drivers."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


def get_gate_inputs(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> GateInputs:
    """FastAPI dependency (overridable in tests)."""
    return read_gate_inputs(db, user)


def missing_requirements(user: User, inputs: GateInputs) -> list[str]:
    """Return unmet requirement codes (empty list means unlocked)."""
    missing: list[str] = []
    if user.level != REQUIRED_LEVEL:
        missing.append("level_4")
    if (
        inputs.progress_pct is None
        or not math.isfinite(inputs.progress_pct)
        or inputs.progress_pct < 100
        or inputs.progress_pct > 100
    ):
        missing.append("plan_progress_100")
    if (
        inputs.brier is None
        or not math.isfinite(inputs.brier)
        or inputs.brier < 0
        or inputs.brier > MAX_BRIER
    ):
        missing.append("brier_lte_0.25")
    return missing


def require_nasdaq_gate(
    user: User = Depends(current_user), inputs: GateInputs = Depends(get_gate_inputs)
) -> User:
    """Dependency: 403 TOOL_LOCKED unless every requirement is met."""
    missing = missing_requirements(user, inputs)
    if missing:
        err = ToolLockedError(
            REQUIRED_LEVEL,
            "Finish Level 4, your full learning plan, and calibration (Brier at or "
            "below 0.25) to open the Nasdaq literacy check.",
        )
        err.extra["missing_requirements"] = missing
        raise err
    return user
