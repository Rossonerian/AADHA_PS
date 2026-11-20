"""Server-side unlock gate for `nasdaq_verifier`. Fails closed when data is missing."""

import json
from contextlib import suppress
from dataclasses import dataclass
from math import isfinite

from fastapi import Depends
from sqlalchemy import Uuid, bindparam, inspect, text
from sqlalchemy.orm import Session

from app.core.auth import User, current_user
from app.core.db import get_db
from app.core.errors import ToolLockedError

REQUIRED_LEVEL = 4
MAX_BRIER = 0.25


@dataclass(frozen=True)
class GateInputs:
    """Learner progress facts the gate needs."""

    progress_pct: float | None
    brier: float | None


def read_gate_inputs(db: Session, user: User) -> GateInputs:
    """Read calculated plan completion and latest mean Brier from Education tables.

    `plans.progress` is a map of lesson ID to status, not a stored percentage. Derive
    completion from the plan's nonempty unique lesson list and status map so the gate
    consumes progress written by actual lesson checks. Missing or malformed rows fail
    closed.
    """
    inspector = inspect(db.get_bind())
    progress: float | None = None
    brier: float | None = None
    owner = bindparam("u", type_=Uuid(as_uuid=False))
    if inspector.has_table("plans"):
        row = db.execute(
            text(
                "SELECT lesson_ids, progress FROM plans WHERE user_id = :u"
            ).bindparams(owner),
            {"u": user.id},
        ).fetchone()
        if row:
            try:
                ids = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                statuses = json.loads(row[1]) if isinstance(row[1], str) else row[1]
                if (
                    isinstance(ids, list)
                    and ids
                    and all(isinstance(x, str) for x in ids)
                    and len(set(ids)) == len(ids)
                    and isinstance(statuses, dict)
                ):
                    progress = (
                        100.0
                        * sum(statuses.get(x) == "completed" for x in ids)
                        / len(ids)
                    )
            except (ValueError, TypeError):
                pass  # Malformed progress is not evidence of completion.
    if inspector.has_table("skill_scores"):
        row = db.execute(
            text(
                "SELECT AVG(brier) FROM (SELECT brier, ROW_NUMBER() OVER "
                "(PARTITION BY skill_area ORDER BY measured_at DESC, id DESC) AS rn "
                "FROM skill_scores WHERE user_id = :u) latest WHERE rn = 1"
            ).bindparams(owner),
            {"u": user.id},
        ).fetchone()
        if row and row[0] is not None:
            with suppress(TypeError, ValueError):
                brier = float(row[0])
    return GateInputs(progress, brier)


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
        or not isfinite(inputs.progress_pct)
        or inputs.progress_pct != 100
    ):
        missing.append("plan_progress_100")
    if (
        inputs.brier is None
        or not isfinite(inputs.brier)
        or not 0 <= inputs.brier <= MAX_BRIER
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
