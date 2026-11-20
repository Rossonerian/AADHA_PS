"""Deterministic flags. Missing market or registry evidence is not a finding."""

import re
from datetime import date, datetime, timedelta
from math import isfinite
from statistics import median

from pandas import notna, to_datetime, to_numeric

from .ports import VerifierCore
from .schemas import DataOrigin, RedFlag, RedFlagCode

_GUARANTEE = re.compile(
    r"\b(?:guaranteed\s+(?:returns?|profits?)|(?:returns?|profits?)\s+guaranteed|"
    r"risk[ -]?free|sure[ -]?shot|pakka\s+(?:munafa|profit|return)|no\s+loss)\b",
    re.IGNORECASE,
)
_URGENCY = re.compile(
    r"\b(?:act\s+now|last\s+chance|limited\s+time|hurry|jaldi|abhi\s+(?:lo|karo)|"
    r"before\s+it(?:['’]s|\s+is)\s+too\s+late|don['’]t\s+miss\s+out)\b",
    re.IGNORECASE,
)


def collect_flags(
    *,
    text: str,
    symbol: str | None,
    applicable_date: date,
    vague: bool,
    registered: bool | None,
    deleted: bool,
    origin: DataOrigin,
    core: VerifierCore,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    def add(
        code: RedFlagCode, message: str, **evidence: str | float | bool | None
    ) -> None:
        flags.append(
            RedFlag(code=code, text=message, evidence=evidence, data_origin=origin)
        )

    if _GUARANTEE.search(text):
        add(
            RedFlagCode.GUARANTEED_RETURNS,
            "The message claims a guaranteed or risk-free return.",
            matched=True,
        )
    if _URGENCY.search(text):
        add(RedFlagCode.URGENCY, "The message uses time pressure.", matched=True)
    if symbol:
        stage = core.market.surveillance(symbol, applicable_date)
        if stage is not None:
            add(
                RedFlagCode.SURVEILLANCE_LIST,
                "The security was on an exchange surveillance list.",
                stage=stage,
                as_of=applicable_date.isoformat(),
            )
        frame = core.market.prices(
            symbol, applicable_date - timedelta(days=50), applicable_date
        )
        column = next(
            (name for name in frame.columns if str(name).casefold() == "volume"), None
        )
        if column is not None:
            date_col = next(
                (col for col in frame.columns if str(col).strip().lower() == "date"),
                None,
            )
            dates = to_datetime(
                frame[date_col] if date_col is not None else frame.index,
                errors="coerce",
            )
            volumes = to_numeric(frame[column], errors="coerce")
            before_post = sorted(
                (day.date(), float(volume))
                for day, volume in zip(dates, volumes, strict=True)
                if isinstance(day, datetime)
                and notna(day)
                and day.date() < applicable_date
                and isfinite(float(volume))
                and float(volume) >= 0
            )
            if before_post:
                # Latest completed session vs. the preceding 20 observed sessions.
                day, latest = before_post[-1]
                baseline = [value for _, value in before_post[-21:-1]]
                if len(baseline) >= 10:
                    typical = median(baseline)
                    if typical > 0 and latest >= 3 * typical:
                        add(
                            RedFlagCode.PRE_POST_VOLUME_SPIKE,
                            "Volume was unusually high before the post.",
                            ratio=round(latest / typical, 2),
                            session=day.isoformat(),
                        )
                if core.market_cap_bucket is not None and len(before_post) >= 10:
                    bucket = core.market_cap_bucket(symbol, applicable_date)
                    typical = median(value for _, value in before_post[-20:])
                    if bucket == "small_cap" and typical < 20_000:
                        add(
                            RedFlagCode.ILLIQUID_SMALL_CAP,
                            "The security was small-cap and had low observed trading volume.",
                            market_cap_bucket=bucket,
                            median_daily_volume=typical,
                        )
    if registered is False:
        add(
            RedFlagCode.NOT_SEBI_REGISTERED,
            "No matching SEBI registration was found for the source.",
            found=False,
        )
    if vague:
        add(
            RedFlagCode.VAGUE_CLAIM,
            "The message does not state a claim that can be measured.",
            scorable=False,
        )
    if deleted:
        add(
            RedFlagCode.DELETED_POST,
            "The original post was confirmed deleted.",
            deleted=True,
        )
    return flags
