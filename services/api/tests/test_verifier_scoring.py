from collections.abc import Sequence
from datetime import date

import pandas as pd
import pytest

from app.verifier.schemas import Direction, SourceLabel
from app.verifier.scoring import evaluate_claim, rate_source

_POST = date(2026, 1, 2)


def _prices(days: list[int], **columns: Sequence[float | None]) -> pd.DataFrame:
    return pd.DataFrame(columns, index=pd.to_datetime([date(2026, 1, day) for day in days]))


@pytest.mark.parametrize("target", [None, 120])
def test_benchmark_uses_exact_sessions_and_same_endpoints(target: float | None) -> None:
    stock = _prices([8, 7, 6, 5, 2], cLoSe=[60, 105, 500, 100, 900])
    index = _prices([2, 5, 8, 7], CLOSE=[500, 100, 180, 102])
    result = evaluate_claim(
        direction=Direction.UP, start=_POST, window_days=2, stock=stock, benchmark=index, target=target
    )
    assert result is not None
    assert result.window_end == date(2026, 1, 7)
    assert result.method == "benchmark_relative"
    assert result.correct
    assert result.stock_pct == pytest.approx(5)
    assert result.index_pct == pytest.approx(2)


def test_one_session_call_uses_same_day_open_to_close() -> None:
    stock = _prices([2, 5], Open=[200, 100], Close=[220, 110])
    benchmark = _prices([2, 5], Open=[150, 100], Close=[120, 101])
    result = evaluate_claim(direction=Direction.UP, start=_POST, window_days=1,
                            stock=stock, benchmark=benchmark)
    assert result is not None and result.correct
    assert result.window_end == date(2026, 1, 5)
    assert result.stock_pct == pytest.approx(10)


@pytest.mark.parametrize("raw_close", [[200, 105], [150, 105]])
def test_adjusted_close_ignores_split_or_bonus_price_drop(raw_close: list[float]) -> None:
    stock = _prices([5, 7], Close=raw_close)
    stock["Adj Close"] = [100, 105]
    result = evaluate_claim(
        direction=Direction.UP, start=_POST, window_days=2,
        stock=stock, benchmark=_prices([5, 7], Close=[100, 102]),
    )
    assert result is not None and result.correct
    assert result.stock_pct == pytest.approx(5)


@pytest.mark.parametrize(
    ("stock_close", "index_close", "direction", "correct"),
    [
        (110, 110, Direction.UP, False),
        (90, 90, Direction.DOWN, False),
        (102, 105, Direction.DOWN, True),
        (95, 90, Direction.DOWN, False),
    ],
)
def test_requires_strictly_positive_signed_excess(
    stock_close: float, index_close: float, direction: Direction, correct: bool
) -> None:
    result = evaluate_claim(
        direction=direction, start=_POST, window_days=2,
        stock=_prices([5, 7], Close=[100, stock_close]),
        benchmark=_prices([5, 7], Close=[100, index_close]),
    )
    assert result is not None and result.correct is correct


@pytest.mark.parametrize(
    ("stock", "index"),
    [
        (_prices([5, 6], Close=[100, 105]), _prices([5, 7], Close=[100, 102])),
        (_prices([6, 7], Close=[100, 105]), _prices([5, 7], Close=[100, 102])),
        (_prices([5, 7], Close=[100, None]), _prices([5, 7], Close=[100, 102])),
        (_prices([5, 7], Close=[100, 105]), _prices([5, 7], Close=[100, None])),
        (_prices([5, 7], Close=[100, 105]), _prices([2, 5, 5], Close=[99, 100, 102])),
    ],
)
def test_missing_endpoints_or_incomplete_window_are_unscorable(
    stock: pd.DataFrame, index: pd.DataFrame
) -> None:
    assert evaluate_claim(
        direction=Direction.UP, start=_POST, window_days=2, stock=stock, benchmark=index
    ) is None


@pytest.mark.parametrize(
    ("direction", "op", "high", "low", "expected"),
    [
        (Direction.UP, [100, 100], [110, 101], [99, 90], True),
        (Direction.UP, [100, 100], [101, 110], [90, 99], False),
        (Direction.UP, [None, 100], [110, 101], [90, 99], None),
        (Direction.UP, [100, 100], [110, 101], [90, 99], None),
        (Direction.UP, [111, 100], [112, 101], [89, 99], True),
        (Direction.DOWN, [89, 100], [111, 101], [88, 99], True),
        (Direction.DOWN, [111, 100], [112, 101], [89, 99], False),
        (Direction.DOWN, [100, 100], [101, 110], [90, 99], True),
        (Direction.UP, [100, 100], [105, 105], [95, 95], False),
    ],
)
def test_bracket_uses_first_touch_and_resolves_gaps_before_intraday_extremes(
    direction: Direction,
    op: list[float | None],
    high: list[float],
    low: list[float],
    expected: bool | None,
) -> None:
    target, stop = (110, 90) if direction == Direction.UP else (90, 110)
    result = evaluate_claim(
        direction=direction, start=_POST, window_days=2, target=target, stop=stop, entry=100,
        stock=_prices([5, 7], oPeN=op, hIgH=high, lOw=low, Close=[100, 105]),
        benchmark=_prices([5, 7], Close=[100, 102]),
    )
    assert result is not None
    assert result.window_end == date(2026, 1, 7)
    assert result.method == ("ambiguous_barrier_order" if expected is None else "target_stop")
    assert result.correct is expected


@pytest.mark.parametrize("hit_day", [5, 7])
def test_missing_bracket_session_only_blocks_if_it_precedes_a_decisive_bar(hit_day: int) -> None:
    result = evaluate_claim(
        direction=Direction.UP, start=_POST, window_days=2, target=110, stop=90,
        stock=_prices([hit_day], Open=[100], High=[111], Low=[99]),
        benchmark=_prices([5, 7], Close=[100, 102]),
    )
    if hit_day == 5:
        assert result is not None and result.correct
        assert result.window_end == date(2026, 1, 7)
    else:
        assert result is None


def test_bracket_ignores_post_day_and_bars_beyond_window() -> None:
    stock = _prices([2, 5, 7, 8], Open=[120, 100, 100, 120], High=[121, 101, 101, 121], Low=[119, 99, 99, 119])
    index = _prices([2, 5, 7, 8], Close=[100, 101, 102, 103])
    result = evaluate_claim(
        direction=Direction.UP, start=_POST, window_days=2, stock=stock, benchmark=index, target=110, stop=90
    )
    assert result is not None and not result.correct


@pytest.mark.parametrize(
    "adjustment",
    [{"Adj Close": [100, 100, 111]}, {"Stock Splits": [0, 0, 2]}, {"Dividends": [0, 1, 0]}],
)
def test_bracket_rejects_detectable_basis_mismatch(adjustment: dict[str, list[float | None]]) -> None:
    stock = _prices(
        [2, 5, 7], Open=[200, 100, 111], High=[201, 101, 112], Low=[199, 99, 110],
        Close=[200, 100, 111], **adjustment,
    )
    assert evaluate_claim(
        direction=Direction.UP, start=_POST, window_days=2, target=110, stop=90,
        stock=stock, benchmark=_prices([5, 7], Close=[100, 102]),
    ) is None


@pytest.mark.parametrize(("entry", "target", "stop"), [(100, 90, 110), (110, 110, 90), (100, 110, 0)])
def test_invalid_explicit_bracket_does_not_silently_change_the_metric(
    entry: float, target: float, stop: float
) -> None:
    assert evaluate_claim(
        direction=Direction.UP, start=_POST, window_days=2, entry=entry, target=target, stop=stop,
        stock=_prices([5, 7], Close=[100, 120]), benchmark=_prices([5, 7], Close=[100, 102]),
    ) is None


@pytest.mark.parametrize(("registered", "expected"), [(True, 69), (None, 63), (False, 56)])
def test_source_formula_includes_shrinkage_and_neutral_unknown_registration(
    registered: bool | None, expected: int
) -> None:
    score, _ = rate_source(scored=6, correct=4, tracked=10, deleted=2, registered=registered, flagged=3)
    assert score == expected


@pytest.mark.parametrize(
    ("scored", "correct", "deleted", "registered", "flagged", "score", "label"),
    [
        (4, 4, 0, True, 0, 85, SourceLabel.NOT_ENOUGH_HISTORY),
        (5, 5, 0, True, 0, 87, SourceLabel.RELIABLE),
        (6, 3, 4, True, 0, 65, SourceLabel.RELIABLE),
        (6, 3, 2, True, 2, 64, SourceLabel.SEMI_RELIABLE),
        (6, 2, 2, False, 6, 40, SourceLabel.SEMI_RELIABLE),
        (6, 2, 4, False, 5, 39, SourceLabel.NOT_RELIABLE),
        (6, -1, 100, False, 100, 12, SourceLabel.NOT_RELIABLE),
        (6, 100, -1, True, -1, 88, SourceLabel.RELIABLE),
    ],
)
def test_source_rating_thresholds_and_bounded_counts(
    scored: int, correct: int, deleted: int, registered: bool, flagged: int, score: int, label: SourceLabel
) -> None:
    assert rate_source(
        scored=scored, correct=correct, tracked=10, deleted=deleted, registered=registered, flagged=flagged
    ) == (score, label)


def test_source_without_evidence_is_neutral() -> None:
    assert rate_source(scored=0, correct=0, tracked=0, deleted=0, registered=None, flagged=0) == (
        50, SourceLabel.NOT_ENOUGH_HISTORY
    )
