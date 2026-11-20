"""Adjusted daily OHLCV equity and benchmark index loader with atomic CSV cache."""

from __future__ import annotations

import os
import re
import uuid
from datetime import date as DateType
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]

from app.core.logging import get_logger
from app.core.market.symbols import (
    canonicalize_ticker,
    get_market_data_dir,
    is_test_env,
)

_logger = get_logger("aacharya.market.prices")

PRICE_COLUMNS: list[str] = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "symbol",
    "source",
    "as_of_date",
    "data_origin",
]

INDEX_MAP: dict[str, tuple[str, str, str]] = {
    "NIFTY50": ("NIFTY50", "^NSEI", "yfinance:NSE_index"),
    "NIFTY 50": ("NIFTY50", "^NSEI", "yfinance:NSE_index"),
    "^NSEI": ("NIFTY50", "^NSEI", "yfinance:NSE_index"),
    "SENSEX": ("SENSEX", "^BSESN", "yfinance:BSE_index"),
    "BSE SENSEX": ("SENSEX", "^BSESN", "yfinance:BSE_index"),
    "^BSESN": ("SENSEX", "^BSESN", "yfinance:BSE_index"),
}

_WHITESPACE_RE = re.compile(r"\s+")


def _empty_price_df() -> pd.DataFrame:
    df = pd.DataFrame(columns=PRICE_COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    return df


def parse_market_date(value: DateType | datetime | pd.Timestamp | str) -> DateType:
    """Parse a date, datetime, Timestamp, or ISO YYYY-MM-DD string into `datetime.date`."""
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, DateType):
        return value
    return DateType.fromisoformat(str(value).strip()[:10])


def _standardize_frame(
    df: pd.DataFrame,
    *,
    canonical_symbol: str,
    default_source: str,
) -> pd.DataFrame:
    if df.empty:
        return _empty_price_df()

    work = df.copy()
    work["date"] = (
        pd.to_datetime(work["date"], errors="coerce")
        .dt.tz_localize(None)
        .dt.normalize()
    )
    work = work.dropna(subset=["date", "close"])
    if work.empty:
        return _empty_price_df()

    for col in ("open", "high", "low", "close"):
        work[col] = pd.to_numeric(work[col], errors="coerce").astype("float64")
    work["volume"] = (
        pd.to_numeric(work["volume"], errors="coerce").fillna(0).astype("int64")
    )

    work = work.dropna(subset=["open", "high", "low", "close"])
    if work.empty:
        return _empty_price_df()

    work = work.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    max_date_str = work["date"].max().strftime("%Y-%m-%d")
    work["symbol"] = canonical_symbol
    if "source" not in work.columns or work["source"].isna().all():
        work["source"] = default_source
    else:
        work["source"] = work["source"].fillna(default_source).astype(str)
    work["as_of_date"] = max_date_str
    work["data_origin"] = "real"

    return work[PRICE_COLUMNS].reset_index(drop=True)


def _read_cached_csv(
    csv_path: Path,
    *,
    canonical_symbol: str,
    default_source: str,
) -> pd.DataFrame:
    if not csv_path.exists():
        return _empty_price_df()
    try:
        raw = pd.read_csv(csv_path)
    except Exception as exc:
        _logger.warning(
            "price_cache_read_failed",
            extra={"path": str(csv_path), "error": str(exc)},
        )
        return _empty_price_df()
    return _standardize_frame(
        raw, canonical_symbol=canonical_symbol, default_source=default_source
    )


def _write_csv_atomic(csv_path: Path, df: pd.DataFrame) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    tmp_path = (
        csv_path.parent / f".{csv_path.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        out[PRICE_COLUMNS].to_csv(tmp_path, index=False)
        os.replace(tmp_path, csv_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _fetch_yfinance_history(
    ticker_candidates: list[tuple[str, str]],
    start_date: DateType,
    end_date: DateType,
    canonical_symbol: str,
) -> pd.DataFrame:
    yf_end = (end_date + timedelta(days=1)).isoformat()
    yf_start = start_date.isoformat()

    for yf_ticker, source_label in ticker_candidates:
        try:
            hist = yf.Ticker(yf_ticker).history(
                start=yf_start,
                end=yf_end,
                auto_adjust=True,
            )
        except Exception as exc:
            _logger.warning(
                "yfinance_fetch_failed",
                extra={"ticker": yf_ticker, "error": str(exc)},
            )
            continue

        if hist is None or hist.empty:
            continue

        frame = hist.reset_index()
        date_col = "Date" if "Date" in frame.columns else frame.columns[0]
        renamed = pd.DataFrame(
            {
                "date": frame[date_col],
                "open": frame["Open"],
                "high": frame["High"],
                "low": frame["Low"],
                "close": frame["Close"],
                "volume": frame["Volume"],
                "symbol": canonical_symbol,
                "source": source_label,
                "as_of_date": "",
                "data_origin": "real",
            }
        )
        standardized = _standardize_frame(
            renamed,
            canonical_symbol=canonical_symbol,
            default_source=source_label,
        )
        if not standardized.empty:
            return standardized

    return _empty_price_df()


def _load_or_fetch_ohlcv(
    *,
    cache_key: str,
    canonical_symbol: str,
    ticker_candidates: list[tuple[str, str]],
    start_date: DateType,
    end_date: DateType,
    allow_live: bool | None,
) -> pd.DataFrame:
    if start_date > end_date:
        raise ValueError(f"start ({start_date}) must be <= end ({end_date})")

    market_dir = get_market_data_dir()
    csv_path = market_dir / "prices" / f"{cache_key}.csv"
    default_source = ticker_candidates[0][1]

    cached = _read_cached_csv(
        csv_path,
        canonical_symbol=canonical_symbol,
        default_source=default_source,
    )

    live_enabled = allow_live if allow_live is not None else (not is_test_env())

    needs_fetch = cached.empty
    if not cached.empty:
        cached_min = cached["date"].min().date()
        cached_max = cached["date"].max().date()
        if end_date > cached_max or start_date < cached_min:
            needs_fetch = True

    if needs_fetch and live_enabled:
        fetch_start = start_date
        fetch_end = end_date
        if not cached.empty:
            cached_min = cached["date"].min().date()
            cached_max = cached["date"].max().date()
            fetch_start = (
                min(start_date, cached_min)
                if start_date < cached_min
                else max(start_date, cached_max - timedelta(days=7))
            )
            fetch_end = max(end_date, cached_max)

        fetched = _fetch_yfinance_history(
            ticker_candidates,
            fetch_start,
            fetch_end,
            canonical_symbol,
        )
        if not fetched.empty:
            if cached.empty:
                merged = fetched
            else:
                combined = pd.concat([cached, fetched], ignore_index=True)
                merged = _standardize_frame(
                    combined,
                    canonical_symbol=canonical_symbol,
                    default_source=str(fetched["source"].iloc[-1]),
                )
            _write_csv_atomic(csv_path, merged)
            cached = merged
        elif not cached.empty:
            _logger.warning(
                "yfinance_fallback_to_cache",
                extra={
                    "symbol": canonical_symbol,
                    "start": str(start_date),
                    "end": str(end_date),
                },
            )

    if cached.empty:
        return _empty_price_df()

    mask = (cached["date"] >= pd.Timestamp(start_date)) & (
        cached["date"] <= pd.Timestamp(end_date)
    )
    return cached.loc[mask].reset_index(drop=True)


def prices(
    symbol: str,
    start: DateType | str,
    end: DateType | str,
    *,
    allow_live: bool | None = None,
) -> pd.DataFrame:
    """Return split/dividend-adjusted daily OHLCV DataFrame for an NSE/BSE equity symbol."""
    raw = symbol.strip()
    if not raw:
        raise ValueError("Symbol must not be empty")

    explicit_bse = bool(re.search(r"\.BO$", raw, flags=re.IGNORECASE))
    canonical = canonicalize_ticker(raw)
    if not canonical:
        raise ValueError(f"Could not normalize symbol: {symbol}")

    start_date = parse_market_date(start)
    end_date = parse_market_date(end)

    if explicit_bse:
        candidates = [
            (f"{canonical}.BO", "yfinance:BSE_adjusted"),
            (f"{canonical}.NS", "yfinance:NSE_adjusted"),
        ]
    else:
        candidates = [
            (f"{canonical}.NS", "yfinance:NSE_adjusted"),
            (f"{canonical}.BO", "yfinance:BSE_adjusted"),
        ]

    return _load_or_fetch_ohlcv(
        cache_key=canonical,
        canonical_symbol=canonical,
        ticker_candidates=candidates,
        start_date=start_date,
        end_date=end_date,
        allow_live=allow_live,
    )


def index(
    name: str,
    start: DateType | str,
    end: DateType | str,
    *,
    allow_live: bool | None = None,
) -> pd.DataFrame:
    """Return daily OHLCV DataFrame for benchmark index (`NIFTY50` or `SENSEX`)."""
    normalized_key = _WHITESPACE_RE.sub(" ", name.strip().upper())
    mapping = INDEX_MAP.get(normalized_key)
    if mapping is None:
        raise ValueError(
            f"Unknown benchmark index '{name}'. Supported indices: NIFTY50, SENSEX."
        )

    cache_key, yf_ticker, source_label = mapping
    start_date = parse_market_date(start)
    end_date = parse_market_date(end)

    return _load_or_fetch_ohlcv(
        cache_key=cache_key,
        canonical_symbol=cache_key,
        ticker_candidates=[(yf_ticker, source_label)],
        start_date=start_date,
        end_date=end_date,
        allow_live=allow_live,
    )
