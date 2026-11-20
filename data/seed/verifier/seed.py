"""Seed six explicitly synthetic personas. Run after the Verifier migration."""

from argparse import ArgumentParser
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.verifier.ingestion import ingest
from app.verifier.models import Claim, Submission
from app.verifier.repository import save_submission, source_for, update_rating
from app.verifier.schemas import (
    ClaimOutcome,
    DataOrigin,
    Direction,
    RedFlag,
    RedFlagCode,
)
from app.verifier.scoring import evaluate_claim
from pandas import DataFrame, bdate_range
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DEMO_TIP = (
    "[15/01/2025, 09:15] Demo Forward Desk: "
    "XYZDEMO will rise this week. Pakka munafa, last chance!"
)
PERSONAS = {
    "demo-accurate": (True, True, True, True, True),
    "demo-random": (False, True, False, True, False),
    "demo-forward-desk": (False, False, False, False, False),
    "demo-vague": (False, True, True, False, True),
    "demo-deleter": (True, False, True, True, False),
    "demo-derivatives": (False, False, False, True, True),
}


def load(sessions: sessionmaker[Session], owner: UUID) -> None:
    origin = DataOrigin.SYNTHETIC
    with sessions.begin() as session:
        for handle, wins in PERSONAS.items():
            source = source_for(
                session,
                "whatsapp" if handle == "demo-forward-desk" else "demo",
                handle,
                origin,
            )
            source.sebi_registered = (
                handle == "demo-accurate" if handle != "demo-vague" else None
            )
            for n, correct in enumerate(wins):
                day = datetime(2025, 1, 15, 4, tzinfo=UTC) + timedelta(weeks=n)
                is_pumper = handle == "demo-forward-desk"
                text = (
                    DEMO_TIP
                    if is_pumper and n == 0
                    else (
                        f"{handle} card {n + 1}: XYZDEMO will rise this week."
                        + (" Guaranteed returns, last chance!" if is_pumper else "")
                        + (
                            " Discussion in a futures and options group."
                            if handle == "demo-derivatives"
                            else ""
                        )
                    )
                )
                flags = []
                if is_pumper:
                    flags = [
                        RedFlag(
                            code=RedFlagCode.GUARANTEED_RETURNS,
                            text="The message claims a guaranteed return.",
                            evidence={"matched": True},
                            data_origin=origin,
                        ),
                        RedFlag(
                            code=RedFlagCode.URGENCY,
                            text="The message uses time pressure.",
                            evidence={"matched": True},
                            data_origin=origin,
                        ),
                        RedFlag(
                            code=RedFlagCode.NOT_SEBI_REGISTERED,
                            text="This fictional source is not SEBI registered.",
                            evidence={"found": False},
                            data_origin=origin,
                        ),
                    ]
                sessions_index = bdate_range(
                    start=day.date() + timedelta(days=1), periods=5
                )
                stock = DataFrame(
                    {"Close": [100, 100, 100, 100, 108 if correct else 92]},
                    index=sessions_index,
                )
                index = DataFrame({"Close": [100] * 5}, index=sessions_index)
                score = evaluate_claim(
                    direction=Direction.UP,
                    start=day.date(),
                    window_days=5,
                    stock=stock,
                    benchmark=index,
                )
                if score is None or score.correct is None:
                    raise ValueError("Synthetic benchmark data has no scorable window")
                outcome = ClaimOutcome(
                    correct=score.correct,
                    method=score.method,
                    stock_pct=score.stock_pct,
                    index_pct=score.index_pct,
                    data_origin=origin,
                )
                _save(
                    session,
                    owner,
                    source.id,
                    day,
                    text,
                    flags,
                    outcome,
                    score.window_end,
                    deleted=handle == "demo-deleter" and n < 4,
                )
            if handle == "demo-vague":
                for n, fragment in enumerate(
                    (
                        "Big things soon",
                        "Hidden gem on the horizon",
                        "Wait for the rocket",
                        "Our next multibagger could be anywhere",
                        "Watch this space",
                    )
                ):
                    _save(
                        session,
                        owner,
                        source.id,
                        datetime(2025, 3, n + 1, tzinfo=UTC),
                        fragment,
                        [
                            RedFlag(
                                code=RedFlagCode.VAGUE_CLAIM,
                                text="The message does not state a measurable claim.",
                                evidence={"scorable": False},
                                data_origin=origin,
                            ),
                        ],
                        None,
                        None,
                    )
            update_rating(session, source)


def _save(
    session: Session,
    owner: UUID,
    source: UUID,
    day: datetime,
    text: str,
    flags: list[RedFlag],
    outcome: ClaimOutcome | None,
    end: date | None,
    *,
    deleted: bool = False,
) -> None:
    tip = ingest(text=text, url=None, image_base64=None, now=day)
    origin = DataOrigin.SYNTHETIC
    save_submission(
        session,
        Submission(
            user_id=owner,
            source_id=source,
            raw_content=tip.text,
            content_hash=tip.content_hash,
            captured_at=day,
            published_at=day,
            deleted_at=day + timedelta(days=10) if deleted else None,
            red_flags=[flag.model_dump(mode="json") for flag in flags],
            data_origin=origin,
        ),
        Claim(
            symbol="XYZDEMO" if outcome else None,
            direction=Direction.UP if outcome else None,
            window_days=5 if outcome else 20,
            window_end=end,
            status="scored" if outcome else "unscorable",
            scorable=outcome is not None,
            outcome=outcome.model_dump(mode="json") if outcome else None,
            rating_eligible=True,
            data_origin=origin,
        ),
    )


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--owner",
        required=True,
        type=UUID,
        help="Existing platform user UUID for seed evidence",
    )
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    engine = create_engine(args.database_url)
    try:
        load(sessionmaker(engine), args.owner)
    finally:
        engine.dispose()
    print(f"Seeded {len(PERSONAS)} synthetic Verifier sources.")


if __name__ == "__main__":
    main()
