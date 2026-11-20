"""`/api/v1/nasdaq-verifier/*` endpoints (gated server-side)."""

import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.auth import User
from app.core.errors import AppError, NotFoundError
from app.core.finnhub import FinnhubClient, get_finnhub, normalize_symbol
from app.nasdaq_verifier import service
from app.nasdaq_verifier.gate import require_nasdaq_gate

router = APIRouter(prefix="/nasdaq-verifier", tags=["nasdaq-verifier"])


class AnswerIn(BaseModel):
    """One answer with 50–100 confidence."""

    question_id: str
    answer: str
    confidence: int = Field(ge=50, le=100)


class SubmitIn(BaseModel):
    """Submission body."""

    challenge_id: str
    answers: list[AnswerIn]


@router.get("/challenge")
def challenge(
    user: Annotated[User, Depends(require_nasdaq_gate)],
    fh: Annotated[FinnhubClient, Depends(get_finnhub)],
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
    cid, public = service.issue(user.id, questions)
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
    body: SubmitIn, user: Annotated[User, Depends(require_nasdaq_gate)]
) -> dict[str, Any]:
    """Score answers (accuracy + Brier); each challenge can be submitted once."""
    ch = service._store.pop(body.challenge_id, None)
    if ch is None or ch.user_id != user.id or ch.expires < time.time():
        raise NotFoundError("Challenge not found or expired.")
    return service.score(ch, [a.model_dump() for a in body.answers])
