"""Historical facts and private monotone quality index (not a probability).

v1: mean of available bounded components: historical move frequency;
1/(1+required directional move/10); 1-min(positive directional run-up/50,1);
1/max(volume ratio,1); 1-small-cap-illiquidity; 1-surveillance.
Risk distances remain descriptive, avoiding offsetting a harder target with a
larger reward/risk ratio. Missing values are omitted, never zero.
No fitted coefficients, future outcomes or social search inputs. Weight stays
deployment-configured at zero; this descriptive index is not calibrated.
"""

from datetime import date, timedelta
from math import isfinite
from statistics import mean, median
from typing import Any

import pandas as pd

from .ports import VerifierCore
from .schemas import DataOrigin, Direction
from .scoring import _sessions

VERSION = "tip-quality-v1"
CODES = (
    "required_move_pct",
    "move_base_rate",
    "pre_post_run_up_pct",
    "pre_post_volume_ratio",
    "illiquid_small_cap",
    "surveillance_list",
    "stop_distance_pct",
    "reward_risk",
)


def historical(frame: pd.DataFrame, posted: date) -> pd.DataFrame:
    """Re-filter even if a market provider ignores the requested end date."""
    result = frame.copy()
    result.columns = [str(c).strip().lower() for c in result.columns]
    dates = _sessions(result)
    valid = (
        dates.notna()
        & ~dates.duplicated(keep=False)
        & (dates < pd.Timestamp(posted))
        & (dates >= pd.Timestamp(posted - timedelta(days=1096)))
    )
    result = result.loc[valid].copy()
    result.index = dates[valid]
    return result.sort_index()


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (TypeError, ValueError):
        return None


def compute(
    *,
    symbol: str | None,
    direction: str | None,
    target: float | None,
    stop: float | None,
    window: int,
    posted: date | None,
    core: VerifierCore,
    origin: DataOrigin,
) -> dict[str, Any]:
    values: dict[str, Any] = dict.fromkeys(CODES)
    output: dict[str, Any] = {
        "signals": values,
        "as_of": str(posted) if posted else None,
        "version": VERSION,
        "data_origin": str(origin),
        "tip_quality_score": None,
    }
    if (
        not symbol
        or not posted
        or direction not in ("up", "down")
        or not 1 <= window <= 252
    ):
        return output
    try:
        stock = historical(
            core.market.prices(
                symbol, posted - timedelta(days=1096), posted - timedelta(days=1)
            ),
            posted,
        )
        benchmark = historical(
            core.market.index(
                "NIFTY50", posted - timedelta(days=1096), posted - timedelta(days=1)
            ),
            posted,
        )
    except (OSError, RuntimeError, ValueError):
        return output
    if stock.empty or "close" not in stock:
        return output
    if (
        origin == DataOrigin.REAL
        and "data_origin" in stock
        and not stock.data_origin.eq("real").all()
    ):
        return output
    close = pd.to_numeric(stock["close"], errors="coerce")
    close = close.where(close.gt(0)).replace(
        [float("inf"), -float("inf")], float("nan")
    )
    last = _number(close.iloc[-1])
    sign = 1 if direction == Direction.UP else -1
    if last is None or last <= 0:
        return output
    # A visible nominal/adjusted mismatch cannot support comparing quoted levels.
    comparable = (
        origin == DataOrigin.SYNTHETIC
        or (
            core.nominal_price_basis is not None
            and core.nominal_price_basis(
                symbol, posted - timedelta(days=1096), posted - timedelta(days=1)
            )
        )
    ) and not (
        "adj close" in stock
        and not pd.to_numeric(stock["adj close"], errors="coerce").equals(close)
    )
    if target is not None and target > 0 and comparable:
        values["required_move_pct"] = (target / last - 1) * 100
    if len(close) >= 11 and (earlier := _number(close.iloc[-11])) is not None:
        values["pre_post_run_up_pct"] = (last / earlier - 1) * 100
    volume = pd.to_numeric(stock.get("volume", pd.Series(dtype=float)), errors="coerce")
    volume = volume.where(volume.ge(0)).replace(
        [float("inf"), -float("inf")], float("nan")
    )
    if len(volume) >= 65 and volume.iloc[-65:].notna().all():
        baseline = float(volume.iloc[-65:-5].mean())
        if baseline > 0:
            values["pre_post_volume_ratio"] = float(volume.iloc[-5:].mean()) / baseline
    # A dated classification is optional. Missing evidence is not a false flag.
    before = posted - timedelta(days=1)
    if (
        core.market_cap_bucket is not None
        and len(volume) >= 20
        and volume.iloc[-20:].notna().all()
    ):
        bucket = core.market_cap_bucket(symbol, before)
        if bucket is not None:
            values["illiquid_small_cap"] = (
                bucket == "small_cap" and median(volume.iloc[-20:]) < 20_000
            )
    stage = core.market.surveillance(symbol, before)
    if stage is not None:
        values["surveillance_list"] = str(stage)
    if target is not None and stop is not None and comparable:
        reward, risk = sign * (target - last), sign * (last - stop)
        if risk > 0 and reward > 0:
            values["stop_distance_pct"] = risk / last * 100
            values["reward_risk"] = reward / risk
    # Use complete benchmark sessions, so missing equity days cannot shorten N.
    if (
        (target is None or values["required_move_pct"] is not None)
        and not benchmark.empty
        and "close" in benchmark
        and (
            origin != DataOrigin.REAL
            or "data_origin" not in benchmark
            or benchmark.data_origin.eq("real").all()
        )
    ):
        aligned = stock.reindex(benchmark.index)
        prices = (
            pd.to_numeric(aligned.get("adj close", aligned["close"]), errors="coerce")
            .where(lambda s: s.gt(0))
            .replace([float("inf"), -float("inf")], float("nan"))
        )
        index_prices = (
            pd.to_numeric(
                benchmark.get("adj close", benchmark["close"]), errors="coerce"
            )
            .where(lambda s: s.gt(0))
            .replace([float("inf"), -float("inf")], float("nan"))
        )
        if target is not None and values["required_move_pct"] is not None:
            change = (prices / prices.shift(window) - 1) * sign * 100
            valid = prices.notna().rolling(window + 1).sum().eq(window + 1)
            successes = change >= sign * values["required_move_pct"]
        else:
            if window == 1:
                openings = (
                    pd.to_numeric(
                        aligned.get(
                            "open", pd.Series(index=aligned.index, dtype=float)
                        ),
                        errors="coerce",
                    )
                    .where(lambda s: s.gt(0))
                    .replace([float("inf"), -float("inf")], float("nan"))
                )
                index_openings = (
                    pd.to_numeric(
                        benchmark.get(
                            "open", pd.Series(index=benchmark.index, dtype=float)
                        ),
                        errors="coerce",
                    )
                    .where(lambda s: s.gt(0))
                    .replace([float("inf"), -float("inf")], float("nan"))
                )
                excess = prices / openings - index_prices / index_openings
                valid = excess.notna()
            else:
                excess = prices / prices.shift(
                    window - 1
                ) - index_prices / index_prices.shift(window - 1)
                valid = (
                    (prices.notna() & index_prices.notna())
                    .rolling(window)
                    .sum()
                    .eq(window)
                )
            successes = sign * excess > 0
        if int(valid.sum()) >= 20:
            values["move_base_rate"] = float(successes[valid].mean())
            output["historical_windows"] = int(valid.sum())
    components = []
    if values["move_base_rate"] is not None:
        components.append(values["move_base_rate"])
    if values["required_move_pct"] is not None:
        components.append(1 / (1 + max(0, sign * values["required_move_pct"]) / 10))
    if values["pre_post_run_up_pct"] is not None:
        components.append(1 - min(max(0, sign * values["pre_post_run_up_pct"]) / 50, 1))
    if values["pre_post_volume_ratio"] is not None:
        components.append(1 / max(values["pre_post_volume_ratio"], 1))
    if values["illiquid_small_cap"] is not None:
        components.append(float(not values["illiquid_small_cap"]))
    if values["surveillance_list"] is not None:
        components.append(0.0)
    output["tip_quality_score"] = mean(components) if components else None
    return output


def facts(quality: dict[str, Any] | None, core: VerifierCore) -> list[dict[str, Any]]:
    """Only named historical signals; never serialize the private score."""
    if not quality or not quality.get("as_of"):
        return []
    templates = {
        "required_move_pct": (
            "The quoted level differs from the last pre-publication close"
            " by {v:+.2f}%."
        ),
        "move_base_rate": (
            "The stated move occurred in {pct:.2f}% of observed historica"
            "l windows before publication; this is a historical frequency"
            "."
        ),
        "pre_post_run_up_pct": "Ten-session price change before publication: {v:+.2f}%.",
        "pre_post_volume_ratio": (
            "Average volume in the last five pre-publication sessions was"
            " {v:.2f} times the preceding sixty-session average."
        ),
        "illiquid_small_cap": "Small-cap and low-volume evidence was {flag} before publication.",
        "surveillance_list": "Dated exchange surveillance evidence was present before publication.",
        "stop_distance_pct": "The stated stop differed from the earlier close by {v:.2f}%.",
        "reward_risk": (
            "The stated levels imply a reward-to-risk distance ratio of {"
            "v:.2f} using the pre-publication close."
        ),
    }
    result = []
    for code in CODES:
        value = quality.get("signals", {}).get(code)
        if value is None:
            continue
        text = templates[code].format(
            v=value,
            pct=value * 100 if isinstance(value, (float, int)) else 0,
            flag="present" if value else "absent",
        )
        # A blocked fact is omitted, never replaced by raw provider/model text.
        guard = core.check_output(text)
        if guard.ok:
            result.append(
                {
                    "code": code,
                    "text": guard.text,
                    "value": value,
                    "as_of": quality["as_of"],
                    "data_origin": quality["data_origin"],
                }
            )
    return result
