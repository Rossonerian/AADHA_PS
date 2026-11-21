"""`/api/v1/nasdaq-verifier/*` endpoints (gated server-side)."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import User
from app.core.db import get_db
from app.core.errors import AppError
from app.core.finnhub import FinnhubClient, get_finnhub, normalize_symbol
from app.nasdaq_verifier import service
from app.nasdaq_verifier.gate import require_nasdaq_gate

router = APIRouter(prefix="/nasdaq-verifier", tags=["nasdaq-verifier"])


class AnswerIn(BaseModel):
    """One answer with 50–100 confidence."""

    model_config = ConfigDict(extra="forbid")
    question_id: str = Field(min_length=1, max_length=16)
    answer: str = Field(max_length=128)
    confidence: int = Field(ge=50, le=100, strict=True)


class SubmitIn(BaseModel):
    """Submission body."""

    model_config = ConfigDict(extra="forbid")
    challenge_id: str = Field(min_length=1, max_length=66)
    answers: list[AnswerIn] = Field(max_length=4)


@router.get("/challenge")
def challenge(
    user: Annotated[User, Depends(require_nasdaq_gate)],
    fh: Annotated[FinnhubClient, Depends(get_finnhub)],
    db: Annotated[Session, Depends(get_db)],
    symbol: str = Query("NDX"),
) -> dict[str, Any]:
    """Return a real-data snapshot and 3–4 objective data-reading questions."""
    display, fh_symbol = normalize_symbol(symbol)
    snap = fh.snapshot(fh_symbol, display)
    exchange = str(snap.pop("exchange", None) or "").upper()
    if display != "NDX" and "NASDAQ" not in exchange:
        raise AppError("NOT_NASDAQ", "That symbol isn't listed on Nasdaq.", 422)
    questions = service.build_questions(snap)
    if len(questions) < 3:
        raise AppError("INSUFFICIENT_DATA", "Not enough data to build a check.", 502)
    cid, public = service.issue(db, user.id, questions)
    if display == "NDX":
        snap["name"] = "Nasdaq-100 benchmark (QQQ)"
        url = "https://www.nasdaq.com/market-activity/etf/qqq"
    else:
        url = f"https://www.nasdaq.com/market-activity/stocks/{display.lower()}"
    return {
        "challenge_id": cid,
        "data_origin": "real",
        "as_of": datetime.now(UTC).isoformat(),
        "snapshot": snap,
        "nasdaq_url": url,
        "disclaimer": service.DISCLAIMER,
        "questions": public,
    }


@router.post("/submit")
def submit(
    body: SubmitIn,
    user: Annotated[User, Depends(require_nasdaq_gate)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Score answers (accuracy + Brier); each challenge can be submitted once."""
    return service.submit(
        db, body.challenge_id, user.id, [a.model_dump() for a in body.answers]
    )
