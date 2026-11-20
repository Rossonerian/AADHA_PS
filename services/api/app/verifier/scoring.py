"""Deterministic claim outcomes and source ratings; no persistence or market I/O."""

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from math import isfinite
from typing import Literal, SupportsFloat

import pandas as pd

from .schemas import Direction, SourceLabel


@dataclass(frozen=True, slots=True)
class ScoringResult:
    window_end: date
    correct: bool | None
    method: str
    stock_pct: float | None = None
    index_pct: float | None = None


def _sessions(frame: pd.DataFrame) -> pd.DatetimeIndex:
    # Retain the exchange-local date whether exposed as a `date` column or DatetimeIndex.
    date_col = next(
        (col for col in frame.columns if str(col).strip().lower() == "date"), None
    )
    raw = frame[date_col] if date_col is not None else frame.index
    return (
        pd.DatetimeIndex(pd.to_datetime(raw, errors="coerce"))
        .tz_localize(None)
        .normalize()
    )


def _align(
    frame: pd.DataFrame, sessions: pd.DatetimeIndex, window: pd.DatetimeIndex
) -> pd.DataFrame:
    # A duplicated date is a session, but neither of its bars is authoritative.
    take = sessions.isin(window) & ~sessions.duplicated(keep=False)
    bars = frame.loc[take]
    bars.index = sessions[take]
    bars.columns = [str(column).strip().lower() for column in bars.columns]
    return bars.reindex(window)


def _price(value: object) -> float | None:
    if not isinstance(value, (str, SupportsFloat)):
        return None
    try:
        price = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return price if isfinite(price) and price > 0 else None


def _return_pct(bars: pd.DataFrame, *, single_session: bool) -> float | None:
    # A provider may expose both raw Close and the separate adjusted series.
    close = bars.get("adj close", bars.get("close"))
    if not isinstance(close, pd.Series):
        return None
    if single_session:
        opening = bars.get("open")
        if not isinstance(opening, pd.Series) or "adj close" in bars:
            return (
                None  # Do not compare a nominal open with a separately adjusted close.
            )
        first = _price(opening.iloc[0])
    else:
        first = _price(close.iloc[0])
    last = _price(close.iloc[-1])
    if first is None or last is None:
        return None
    pct = (last / first - 1) * 100
    return pct if isfinite(pct) else None


def _known_basis_mismatch(bars: pd.DataFrame) -> bool:
    close, adjusted = bars.get("close"), bars.get("adj close")
    if isinstance(close, pd.DataFrame) or isinstance(adjusted, pd.DataFrame):
        return True  # An ambiguous price column cannot establish a shared basis.
    if isinstance(close, pd.Series) and isinstance(adjusted, pd.Series):
        for raw_value, adj_value in zip(close, adjusted, strict=True):
            raw, adj = _price(raw_value), _price(adj_value)
            if raw is not None and adj is not None and raw != adj:
                return True
    for action in ("stock splits", "dividends"):
        values = bars.get(action)
        if isinstance(values, pd.Series) and values.fillna(0).ne(0).any():
            return True
    return False


def _bracket_outcome(
    bars: pd.DataFrame, *, direction: Direction, target: float, stop: float
) -> bool | Literal["ambiguous"] | None:
    up = direction == Direction.UP
    for _, bar in bars.iterrows():
        opened = _price(bar.get("open"))
        if opened is not None:
            if (up and opened <= stop) or (not up and opened >= stop):
                return False
            if (up and opened >= target) or (not up and opened <= target):
                return True

        high, low = _price(bar.get("high")), _price(bar.get("low"))
        if high is None or low is None or high < low:
            return None
        stopped = (up and low <= stop) or (not up and high >= stop)
        reached = (up and high >= target) or (not up and low <= target)
        if stopped and reached:
            return "ambiguous"
        if stopped or reached:
            return reached
    return False  # Every session was observed, but the target never traded.


def evaluate_claim(
    *,
    direction: Direction,
    start: date,
    window_days: int,
    stock: pd.DataFrame,
    benchmark: pd.DataFrame,
    entry: float | None = None,
    target: float | None = None,
    stop: float | None = None,
) -> ScoringResult | None:
    """Score the first ``window_days`` benchmark sessions strictly after ``start``.

    Without both barriers, use adjusted first-to-last session closes for both
    returns (session open-to-close for a one-session claim) and require strictly
    positive signed excess. With both barriers,
    require an ordered positive bracket (and entry inside it if supplied), then
    use the first observable barrier touch. Entry is not a fill condition.

    Quoted barriers are nominal. Reject visible adjustment evidence (different
    Close/Adj Close or a split/dividend on the post date or in the window) for
    barrier scoring. With only adjusted OHLCV, callers must establish that the
    quote and bars share a price basis; prices alone cannot identify a split.
    """
    if window_days < 1 or direction not in (Direction.UP, Direction.DOWN):
        return None
    posted = pd.Timestamp(start)
    benchmark_dates = _sessions(benchmark)
    window = (
        benchmark_dates[benchmark_dates > posted].unique().sort_values()[:window_days]
    )
    if len(window) != window_days:
        return None
    window_end = window[-1].date()
    stock_dates = _sessions(stock)

    if target is not None and stop is not None:
        target_price, stop_price = _price(target), _price(stop)
        if target_price is None or stop_price is None:
            return None
        lower, upper = (
            (stop_price, target_price)
            if direction == Direction.UP
            else (target_price, stop_price)
        )
        if lower >= upper:
            return None
        if entry is not None:
            entry_price = _price(entry)
            if entry_price is None or not lower < entry_price < upper:
                return None

        basis_dates = window.insert(0, posted)
        basis_bars = _align(stock, stock_dates, basis_dates)
        if _known_basis_mismatch(basis_bars):
            return None
        correct = _bracket_outcome(
            basis_bars.iloc[1:],
            direction=direction,
            target=target_price,
            stop=stop_price,
        )
        if correct == "ambiguous":
            return ScoringResult(window_end, None, "ambiguous_barrier_order")
        return (
            ScoringResult(window_end, correct, "target_stop")
            if isinstance(correct, bool)
            else None
        )

    endpoints = window[[0, -1]].unique()
    stock_pct = _return_pct(
        _align(stock, stock_dates, endpoints), single_session=window_days == 1
    )
    index_pct = _return_pct(
        _align(benchmark, benchmark_dates, endpoints), single_session=window_days == 1
    )
    if stock_pct is None or index_pct is None:
        return None
    correct = (
        stock_pct > index_pct if direction == Direction.UP else stock_pct < index_pct
    )
    return ScoringResult(
        window_end, correct, "benchmark_relative", stock_pct, index_pct
    )


def rate_source(
    *,
    scored: int,
    correct: int,
    tracked: int,
    deleted: int,
    registered: bool | None,
    flagged: int,
) -> tuple[int, SourceLabel]:
    """Return a rounded 0–100 score and its history-gated label.

    Track record is wins / scored outcomes with two prior wins and two prior
    losses. Transparency equally weights the retained share and registration
    (yes=1, no=0, unknown=½). Red-flag history is the share of tips with no flag.
    Both shares use all tracked tips (including deleted and unscorable); flagged
    counts distinct tips, not individual flags. Empty shares are neutral (½).
    Counts are bounded to their denominators; exact half scores round to even.
    """
    scored, tracked = max(0, scored), max(0, tracked)
    track_record = Fraction(2 + min(scored, max(0, correct)), scored + 4)
    neutral = Fraction(1, 2)
    retention = (
        Fraction(tracked - min(tracked, max(0, deleted)), tracked)
        if tracked
        else neutral
    )
    clean = (
        Fraction(tracked - min(tracked, max(0, flagged)), tracked)
        if tracked
        else neutral
    )
    registration = neutral if registered is None else Fraction(int(registered))
    score = round(
        60 * track_record + Fraction(25, 2) * (retention + registration) + 15 * clean
    )

    if scored < 5:
        label = SourceLabel.NOT_ENOUGH_HISTORY
    elif score >= 65:
        label = SourceLabel.RELIABLE
    elif score >= 40:
        label = SourceLabel.SEMI_RELIABLE
    else:
        label = SourceLabel.NOT_RELIABLE
    return score, label
