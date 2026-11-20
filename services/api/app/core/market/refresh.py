"""Market dataset refresh job and instant manifest date reader."""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from datetime import date as DateType
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from app.core.logging import get_logger
from app.core.market.prices import index, prices
from app.core.market.symbols import canonicalize_ticker, get_market_data_dir

_logger = get_logger("paisaproof.market.refresh")

NSE_EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

CORE_WATCHLIST: tuple[str, ...] = (
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "INFY",
    "ICICIBANK",
    "SBIN",
    "BHARTIARTL",
    "ITC",
    "LT",
    "HINDUNILVR",
    "KOTAKBANK",
    "AXISBANK",
    "BAJFINANCE",
    "MARUTI",
    "TMPV",
    "TMCV",
    "WIPRO",
    "SUZLON",
    "YESBANK",
    "RVNL",
    "IRFC",
    "COCHINSHIP",
    "PAYTM",
    "DMART",
    "ETERNAL",
    "IDEA",
    "ADANIENT",
    "SUNPHARMA",
    "HCLTECH",
    "TITAN",
    "ASIANPAINT",
    "NTPC",
    "POWERGRID",
    "ONGC",
    "TATASTEEL",
)

CORE_INDICES: tuple[str, ...] = ("NIFTY50", "SENSEX")


def get_market_data_as_of() -> str | None:
    """Return latest market `as_of_date` (`YYYY-MM-DD`) from `manifest.json` without network I/O."""
    manifest_path = get_market_data_dir() / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _logger.warning(
            "market_manifest_read_failed",
            extra={"path": str(manifest_path), "error": str(exc)},
        )
        return None
    if not isinstance(raw, dict):
        return None
    as_of = raw.get("as_of_date")
    if isinstance(as_of, str) and as_of.strip():
        return as_of.strip()
    return None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _try_refresh_nse_symbols(market_dir: Path, today_str: str) -> str:
    """Attempt standard HTTP GET of NSE EQUITY_L.csv; preserve curated file if blocked."""
    try:
        response = httpx.get(
            NSE_EQUITY_LIST_URL,
            timeout=10.0,
            follow_redirects=True,
        )
        if response.status_code != 200 or "SYMBOL" not in response.text[:200]:
            _logger.info(
                "nse_equity_list_skipped",
                extra={"status_code": response.status_code},
            )
            return f"skipped_http_{response.status_code}"
    except Exception as exc:
        _logger.info(
            "nse_equity_list_skipped",
            extra={"reason": str(exc)},
        )
        return "skipped_unavailable"

    reader = csv.DictReader(io.StringIO(response.text))
    parsed_rows: list[dict[str, str]] = []
    for row in reader:
        sym = (row.get("SYMBOL") or "").strip().upper()
        name = (row.get("NAME OF COMPANY") or "").strip()
        series = (row.get(" SERIES") or row.get("SERIES") or "EQ").strip().upper()
        isin = (row.get(" ISIN NUMBER") or row.get("ISIN NUMBER") or "").strip().upper()
        if sym and name and series in {"EQ", "BE", "BZ", "SM"}:
            parsed_rows.append(
                {
                    "symbol": sym,
                    "company_name": name,
                    "series": series,
                    "isin": isin,
                    "data_origin": "real",
                    "source": "NSE EQUITY_L.csv",
                    "as_of_date": today_str,
                }
            )

    if len(parsed_rows) < 100:
        return "skipped_unexpected_csv"

    csv_path = market_dir / "nse_symbols.csv"
    tmp_path = csv_path.parent / f".nse_symbols.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    fieldnames = [
        "symbol",
        "company_name",
        "series",
        "isin",
        "data_origin",
        "source",
        "as_of_date",
    ]
    try:
        with tmp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(parsed_rows)
        os.replace(tmp_path, csv_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return "updated"


def _scan_max_cached_date(prices_dir: Path) -> str | None:
    if not prices_dir.exists():
        return None
    max_date: str | None = None
    for csv_file in sorted(prices_dir.glob("*.csv")):
        try:
            df = pd.read_csv(csv_file, usecols=["date"])
        except Exception:
            continue
        if df.empty:
            continue
        col_max = str(df["date"].dropna().astype(str).max())[:10]
        if col_max and (max_date is None or col_max > max_date):
            max_date = col_max
    return max_date


def refresh_all(
    symbols: list[str] | None = None,
    *,
    lookback_days: int = 1100,
    fetch_nse_list: bool = True,
) -> dict[str, Any]:
    """Refresh NSE symbol metadata, indices, and OHLCV caches and update `manifest.json`."""
    market_dir = get_market_data_dir()
    market_dir.mkdir(parents=True, exist_ok=True)
    (market_dir / "prices").mkdir(parents=True, exist_ok=True)

    end_date = DateType.today()
    start_date = end_date - timedelta(days=lookback_days)
    today_str = end_date.isoformat()

    nse_status = (
        _try_refresh_nse_symbols(market_dir, today_str)
        if fetch_nse_list
        else "skipped_disabled"
    )

    target_symbols = (
        [canonicalize_ticker(sym) for sym in symbols if sym.strip()]
        if symbols is not None
        else list(CORE_WATCHLIST)
    )

    indices_cached: list[str] = []
    symbols_cached: list[str] = []
    failed_symbols: list[str] = []

    for idx_name in CORE_INDICES:
        df = index(idx_name, start_date, end_date, allow_live=True)
        if df.empty:
            failed_symbols.append(idx_name)
        else:
            indices_cached.append(idx_name)

    for sym in target_symbols:
        df = prices(sym, start_date, end_date, allow_live=True)
        if df.empty:
            failed_symbols.append(sym)
        else:
            symbols_cached.append(sym)

    as_of_date = _scan_max_cached_date(market_dir / "prices")

    manifest_payload: dict[str, Any] = {
        "as_of_date": as_of_date,
        "updated_at": datetime.now(tz=UTC).isoformat(),
        "symbols_cached": sorted(set(symbols_cached)),
        "indices_cached": sorted(set(indices_cached)),
        "failed_symbols": failed_symbols,
        "nse_equity_list_status": nse_status,
        "sources": {
            "prices": "yfinance (.NS/.BO split-and-dividend adjusted daily OHLCV)",
            "indices": "yfinance (^NSEI, ^BSESN daily OHLCV)",
            "symbols": "NSE equity listing & Yahoo Finance verified metadata",
            "surveillance": "NSE ASM/GSM surveillance framework disclosures",
            "sebi": (
                "SEBI Registered Research Analyst (RA) & "
                "Investment Adviser (IA) public records"
            ),
        },
        "data_origin": "real",
    }
    _write_json_atomic(market_dir / "manifest.json", manifest_payload)

    if not failed_symbols:
        status = "ok"
    elif symbols_cached or indices_cached:
        status = "partial"
    else:
        status = "error"
    summary: dict[str, Any] = {
        "status": status,
        "as_of": as_of_date,
        "symbols_cached": len(symbols_cached),
        "indices_cached": len(indices_cached),
        "failed": failed_symbols,
        "nse_equity_list_status": nse_status,
    }
    _logger.info("market_refresh_completed", extra=summary)
    return summary
