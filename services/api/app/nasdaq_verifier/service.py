"""Deterministic question generation and Brier scoring. All numbers come from the snapshot."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.core.guardrails import check_output
from app.nasdaq_verifier.models import NasdaqChallenge

DISCLAIMER = (
    "Educational literacy check only — PaisaProof never recommends buying, selling, "
    "or holding any security."
)
CHALLENGE_TTL = 1800


@dataclass
class Challenge:
    """Server-held answer key for one issued challenge."""

    user_id: str
    answers: dict[str, str]


def _f(v: float) -> str:
    return f"{v:,.2f}"


def _options(correct: str, wrong: list[str], key: int) -> list[str]:
    opts = [*wrong, correct]
    pos = key % len(opts)
    opts[pos], opts[-1] = opts[-1], opts[pos]
    return opts


def _range_q(label: str, lo: float, hi: float) -> dict[str, Any]:
    c = f"{_f(lo)} to {_f(hi)}"
    wrong = [f"{_f(lo * 0.8)} to {_f(hi * 0.9)}", f"{_f(lo * 1.15)} to {_f(hi * 1.2)}"]
    return {"text": label, "options": _options(c, wrong, len(c)), "_answer": c}


def build_questions(snap: dict[str, Any]) -> list[dict[str, Any]]:
    """Return up to 4 factual data-reading questions (with `_answer`, stripped by `issue`)."""
    qs: list[dict[str, Any]] = []
    lo, hi, price = snap.get("week52_low"), snap.get("week52_high"), snap.get("price")
    if lo and hi:
        qs.append(
            _range_q("Which range is the 52-week range shown in the snapshot?", lo, hi)
        )
    if lo and hi and price:
        c = "Upper half" if price >= (lo + hi) / 2 else "Lower half"
        qs.append(
            {
                "text": "Is the latest price in the upper or lower half of its 52-week range?",
                "options": ["Upper half", "Lower half"],
                "_answer": c,
            }
        )
    cap = snap.get("market_cap_musd")
    if cap:
        b = cap / 1000
        c = f"${b:,.1f}B"
        wrong = [f"${b * 0.1:,.1f}B", f"${b * 10:,.1f}B"]
        qs.append(
            {
                "text": "What market capitalization does the snapshot show?",
                "options": _options(c, wrong, int(b)),
                "_answer": c,
            }
        )
    pe = snap.get("pe_ttm")
    if pe:
        c = f"{pe:,.1f}"
        wrong = [f"{pe * 0.5:,.1f}", f"{pe * 2:,.1f}"]
        qs.append(
            {
                "text": "What trailing-twelve-month P/E ratio does the snapshot show?",
                "options": _options(c, wrong, int(pe)),
                "_answer": c,
            }
        )
    day_lo, day_hi = snap.get("day_low"), snap.get("day_high")
    if len(qs) < 4 and day_lo and day_hi:
        qs.append(_range_q("Which range is today's low-to-high range?", day_lo, day_hi))
    for i, q in enumerate(qs, 1):
        q["id"] = f"q{i}"
    return qs[:4]


def issue(
    db: Session, user_id: str, questions: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """Store the answer key; return challenge id and public questions."""
    now = datetime.now(UTC)
    db.execute(delete(NasdaqChallenge).where(NasdaqChallenge.expires_at <= now))
    cid = "c_" + secrets.token_hex(32)
    db.add(
        NasdaqChallenge(
            id=cid,
            user_id=user_id,
            answers={q["id"]: q["_answer"] for q in questions},
            expires_at=now + timedelta(seconds=CHALLENGE_TTL),
            data_origin="real",
        )
    )
    db.commit()
    public = [{k: v for k, v in q.items() if k != "_answer"} for q in questions]
    return cid, public


def submit(
    db: Session, challenge_id: str, user_id: str, answers: list[dict[str, Any]]
) -> dict[str, Any]:
    """Atomically consume an unexpired owned key; a stranger cannot burn it."""
    key = db.execute(
        delete(NasdaqChallenge)
        .where(
            NasdaqChallenge.id == challenge_id,
            NasdaqChallenge.user_id == user_id,
            NasdaqChallenge.expires_at > datetime.now(UTC),
        )
        .returning(NasdaqChallenge.answers)
    ).scalar_one_or_none()
    if key is None:
        raise NotFoundError("Challenge not found or expired.")
    ids = [a["question_id"] for a in answers]
    if len(ids) != len(key) or set(ids) != set(key):
        db.rollback()
        raise AppError(
            "INVALID_ANSWERS", "Answer each challenge question exactly once.", 422
        )
    result = score(Challenge(user_id, key), answers)
    db.commit()
    return result


def score(challenge: Challenge, answers: list[dict[str, Any]]) -> dict[str, Any]:
    """Accuracy + Brier (mean squared gap between confidence and correctness)."""
    results: list[dict[str, Any]] = []
    sq = 0.0
    given = {a["question_id"]: a for a in answers}
    for qid, correct in challenge.answers.items():
        a = given.get(qid)
        ok = a is not None and a["answer"] == correct
        conf = (a["confidence"] if a else 50) / 100
        sq += (conf - (1.0 if ok else 0.0)) ** 2
        results.append(
            {
                "question_id": qid,
                "correct": ok,
                "correct_answer": correct,
                "explanation": f"The snapshot shows {correct}.",
            }
        )
    n = len(results)
    right = sum(1 for r in results if r["correct"])
    brier = round(sq / n, 4)
    fb = check_output(
        f"You read {right} of {n} figures correctly with a Brier score of {brier:.2f}. "
        "Lower Brier means your confidence matched your accuracy."
    )
    return {
        "data_origin": "real",
        "passed": brier <= 0.25,
        "score": round(right / n, 4),
        "brier": brier,
        "results": results,
        "feedback": fb.text,
    }
