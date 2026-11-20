"""Server-side unlock gate for `nasdaq_verifier`. Fails closed when data is missing."""

from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import inspect, text
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
    """Read plan progress and mean Brier from `plans` / `skill_scores` if they exist."""
    inspector = inspect(db.get_bind())
    progress: float | None = None
    brier: float | None = None
    if inspector.has_table("plans"):
        row = db.execute(
            text("SELECT progress FROM plans WHERE user_id = :u"), {"u": user.id}
        ).fetchone()
        if row and row[0] is not None:
            progress = float(row[0])
    if inspector.has_table("skill_scores"):
        row = db.execute(
            text(
                "SELECT AVG(brier) FROM skill_scores WHERE user_id = :u "
                "AND brier IS NOT NULL"
            ),
            {"u": user.id},
        ).fetchone()
        if row and row[0] is not None:
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
    if inputs.progress_pct is None or inputs.progress_pct < 100:
        missing.append("plan_progress_100")
    if inputs.brier is None or inputs.brier > MAX_BRIER:
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
