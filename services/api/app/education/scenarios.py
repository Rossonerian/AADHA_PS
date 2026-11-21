"""Phase 5: Curated 2005+ Indian stock historical scenarios with price-recomputed outcomes."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..core import guardrails, market
from .config import DEFAULT_CONFIG, EducationConfig
from .enums import AttemptContext, AttemptItemType, Direction, ToolName
from .exceptions import NotFoundError, ValidationDomainError
from .learning import require_tool_unlocked
from .repository import EducationRepository

SCENARIO_DISCLAIMER = (
    "Historical learning exercise only — based on past market data, "
    "not investment advice or a future price prediction."
)


def _series_is_real(frame: Any) -> bool:
    """Treat a market series as real only when its rows explicitly say so."""
    if frame.empty or "data_origin" not in frame.columns:
        return False
    origins = {str(value).strip().lower() for value in frame["data_origin"].dropna()}
    return origins == {"real"}


def recompute_scenario_outcome(
    symbol: str,
    as_of_date: str,
    window_days: int,
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Recomputes stock_pct, index_pct (NIFTY50), relative_pct, and actual_direction.

    Prices come from core.market.
    """
    start_dt = date.fromisoformat(str(as_of_date))
    # Pad window slightly to handle weekends/holidays cleanly
    end_dt = start_dt + timedelta(days=int(window_days) + 10)
    target_dt = start_dt + timedelta(days=int(window_days))

    stock_df = market.prices(symbol, start_dt - timedelta(days=7), end_dt)
    idx_df = market.index("NIFTY50", start_dt - timedelta(days=7), end_dt)

    if stock_df.empty or idx_df.empty:
        raise ValidationDomainError(
            "MARKET_DATA_MISSING",
            f"Insufficient market price data to compute outcome for {symbol} around {as_of_date}.",
        )

    start_ts = stock_df["date"].iloc[0].__class__(start_dt)
    target_ts = stock_df["date"].iloc[0].__class__(target_dt)
    index_start_ts = idx_df["date"].iloc[0].__class__(start_dt)
    index_target_ts = idx_df["date"].iloc[0].__class__(target_dt)

    s_entry_rows = stock_df[stock_df["date"] <= start_ts]
    s_exit_rows = stock_df[stock_df["date"] >= target_ts]
    if s_entry_rows.empty or s_exit_rows.empty:
        raise ValidationDomainError(
            "MARKET_DATA_MISSING",
            f"Price data does not cover the complete scenario window for {symbol}.",
        )

    s_entry = float(s_entry_rows.iloc[-1]["close"])
    s_exit = float(s_exit_rows.iloc[0]["close"])

    i_entry_rows = idx_df[idx_df["date"] <= index_start_ts]
    i_exit_rows = idx_df[idx_df["date"] >= index_target_ts]
    if i_entry_rows.empty or i_exit_rows.empty:
        raise ValidationDomainError(
            "MARKET_DATA_MISSING",
            f"Benchmark data does not cover the complete scenario window for {symbol}.",
        )

    i_entry = float(i_entry_rows.iloc[-1]["close"])
    i_exit = float(i_exit_rows.iloc[0]["close"])

    stock_pct = round(100.0 * (s_exit - s_entry) / s_entry, 2)
    index_pct = round(100.0 * (i_exit - i_entry) / i_entry, 2)
    relative_pct = round(stock_pct - index_pct, 2)

    if stock_pct >= cfg.scenario_flat_band_pct:
        actual_direction = Direction.UP.value
    elif stock_pct <= -cfg.scenario_flat_band_pct:
        actual_direction = Direction.DOWN.value
    else:
        actual_direction = Direction.FLAT.value

    return {
        "stock_pct": stock_pct,
        "index_pct": index_pct,
        "relative_pct": relative_pct,
        "actual_direction": actual_direction,
        "entry_close": round(s_entry, 2),
        "exit_close": round(s_exit, 2),
        "data_origin": (
            "real"
            if _series_is_real(stock_df) and _series_is_real(idx_df)
            else "synthetic"
        ),
    }


def scenario_outcome(
    sc: dict[str, Any], cfg: EducationConfig = DEFAULT_CONFIG
) -> tuple[dict[str, Any], str]:
    """Use adjusted market prices when complete; otherwise retain a synthetic seed outcome."""
    try:
        outcome = recompute_scenario_outcome(
            symbol=sc["symbol"],
            as_of_date=sc["as_of_date"],
            window_days=sc["window_days"],
            cfg=cfg,
        )
    except ValidationDomainError as exc:
        if exc.code != "MARKET_DATA_MISSING":
            raise
        return sc["outcome"], "synthetic"
    origin = (
        "real"
        if sc.get("data_origin") == "real" and outcome["data_origin"] == "real"
        else "synthetic"
    )
    return outcome, origin


def build_public_scenario(
    sc: dict[str, Any], *, series_data_origin: str | None = None
) -> dict[str, Any]:
    """Formats scenario context with zero lookahead beyond as_of_date.

    Always includes the explicit disclaimer.
    """
    ctx = dict(sc["context"])
    as_of = str(sc["as_of_date"])
    # Enforce strict no-lookahead filter on chart points
    raw_chart = ctx.get("chart", [])
    safe_chart = [pt for pt in raw_chart if str(pt.get("date", "")) <= as_of]
    return {
        "id": sc["id"],
        "as_of_date": as_of,
        "window_days": int(sc["window_days"]),
        "difficulty": int(sc["difficulty"]),
        "tags": sc.get("tags", []),
        "context": {
            "company": ctx["company"],
            "symbol": sc["symbol"],
            "disclaimer": SCENARIO_DISCLAIMER,
            "chart": safe_chart,
            "headlines": ctx.get("headlines", []),
            "numbers": ctx.get("numbers", {}),
        },
        "data_origin": (
            "real"
            if sc.get("data_origin") == "real" and series_data_origin == "real"
            else "synthetic"
        ),
    }


def get_next_scenario(
    repo: EducationRepository,
    user_id: str,
    user_level: int,
    difficulty: int | None = None,
) -> dict[str, Any]:
    """Returns next unseen historical scenario (enforcing L1 `scenarios` unlock)."""
    require_tool_unlocked(repo, user_id, ToolName.SCENARIOS, user_level=user_level)
    seen = repo.list_seen_item_ids(user_id, AttemptItemType.SCENARIO.value)
    candidates = repo.list_scenarios(difficulty=difficulty, exclude_ids=seen)
    if not candidates and difficulty is not None:
        candidates = repo.list_scenarios(exclude_ids=seen)
    if not candidates:
        # Fallback to full pool if user has completed every single scenario
        candidates = repo.list_scenarios(difficulty=difficulty) or repo.list_scenarios()
    if not candidates:
        raise NotFoundError("NO_SCENARIOS", "No historical scenarios are loaded.")
    _, series_origin = scenario_outcome(candidates[0])
    return build_public_scenario(candidates[0], series_data_origin=series_origin)


def answer_scenario(
    repo: EducationRepository,
    user_id: str,
    user_level: int,
    scenario_id: str,
    direction: str,
    confidence: int,
    clues: list[str],
    context: str = AttemptContext.PRACTICE.value,
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Scores a scenario answer against price-recomputed outcome & NIFTY50, passing guardrails."""
    require_tool_unlocked(repo, user_id, ToolName.SCENARIOS, user_level=user_level)
    if str(direction).lower() not in ("up", "down"):
        raise ValidationDomainError(
            "VALIDATION_ERROR", "Scenario direction must be 'up' or 'down'."
        )
    sc = repo.get_scenario(scenario_id)
    if not sc:
        raise NotFoundError(
            "SCENARIO_NOT_FOUND", f"Scenario '{scenario_id}' not found."
        )

    # Always recompute live from core.market when price series is available (no hand-typed outcomes)
    outcome, data_origin = scenario_outcome(sc, cfg=cfg)
    actual_dir = outcome["actual_direction"]
    is_correct = str(direction).lower() == actual_dir

    repo.record_attempt(
        user_id=user_id,
        item_type=AttemptItemType.SCENARIO.value,
        item_id=scenario_id,
        answer=str(direction).lower(),
        confidence=int(confidence),
        correct=is_correct,
        context=context,
    )

    explanation_text = (
        f"{sc['explanation']} Over the {sc['window_days']}-day historical window "
        f"from {sc['as_of_date']}, "
        f"{sc['symbol']} moved {outcome['stock_pct']:+.2f}% "
        f"while NIFTY50 moved {outcome['index_pct']:+.2f}% "
        f"(relative: {outcome['relative_pct']:+.2f}%). {SCENARIO_DISCLAIMER}"
    )
    safe_explanation = guardrails.check_output(explanation_text).text

    return {
        "correct": is_correct,
        "outcome": {
            "stock_pct": outcome["stock_pct"],
            "index_pct": outcome["index_pct"],
            "relative_pct": outcome["relative_pct"],
            "actual_direction": actual_dir,
        },
        "key_clues": sc.get("key_clues", []),
        "explanation": safe_explanation,
        "data_origin": data_origin,
    }
