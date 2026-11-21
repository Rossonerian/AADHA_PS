"""Finnhub client: factual endpoints only (allowlist), cached, every record `data_origin="real"`."""

import math
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
import yfinance as yf  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.enums import DataOrigin
from app.core.errors import AppError

# Rule: never call recommendation, price-target or upgrade/downgrade endpoints.
ALLOWED_ENDPOINTS: frozenset[str] = frozenset(
    {"/quote", "/stock/profile2", "/stock/metric", "/stock/candle"}
)
BASE_URL = "https://finnhub.io/api/v1"
CACHE_TTL_SECONDS = 60
_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z.\-]{0,9}$")
BENCHMARK_ALIAS = {"NDX": "QQQ"}  # ponytail: index quotes need a paid plan; ETF proxy


class FinnhubUnavailableError(AppError):
    """Raised when the key is missing or Finnhub fails."""

    def __init__(self, message: str) -> None:
        super().__init__("FINNHUB_UNAVAILABLE", message, status_code=503)


def normalize_symbol(raw: str) -> tuple[str, str]:
    """Return (display_symbol, finnhub_symbol); raise 422 AppError if invalid."""
    sym = raw.strip().upper()
    if not _SYMBOL_RE.match(sym):
        raise AppError("INVALID_SYMBOL", "Enter a Nasdaq ticker such as AAPL.", 422)
    return sym, BENCHMARK_ALIAS.get(sym, sym)


class FinnhubClient:
    """Thin cached client returning a neutral factual snapshot."""

    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key if api_key is not None else get_settings().finnhub_api_key
        self._cache: dict[tuple[str, str], tuple[float, Any]] = {}

    def _get(self, path: str, **params: Any) -> Any:
        if path not in ALLOWED_ENDPOINTS:
            raise ValueError(f"Finnhub endpoint not allowed: {path}")
        if not self._key:
            raise FinnhubUnavailableError("Market data is not configured.")
        ck = (path, repr(sorted(params.items())))
        hit = self._cache.get(ck)
        if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
        try:
            resp = requests.get(
                BASE_URL + path,
                params={**params, "token": self._key},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise FinnhubUnavailableError(
                "Market data is unavailable right now."
            ) from exc
        self._cache[ck] = (time.monotonic(), data)
        return data

    def snapshot(self, symbol: str, display: str | None = None) -> dict[str, Any]:
        """Map Finnhub responses to the factual snapshot (numbers only, no opinions)."""
        quote = self._get("/quote", symbol=symbol)
        profile = self._get("/stock/profile2", symbol=symbol) or {}
        metric = (self._get("/stock/metric", symbol=symbol, metric="all") or {}).get(
            "metric", {}
        )
        if not quote or not quote.get("c"):
            raise AppError("SYMBOL_NOT_FOUND", "No market data for that symbol.", 404)
        return {
            "symbol": display or symbol,
            "name": profile.get("name") or (display or symbol),
            "sector": profile.get("finnhubIndustry"),
            "exchange": profile.get("exchange"),
            "price": quote.get("c"),
            "day_low": quote.get("l"),
            "day_high": quote.get("h"),
            "week52_low": metric.get("52WeekLow"),
            "week52_high": metric.get("52WeekHigh"),
            "market_cap_musd": profile.get("marketCapitalization"),
            "pe_ttm": metric.get("peTTM") or metric.get("peBasicExclExtraTTM"),
            "chart": self._chart(symbol),
            "data_origin": DataOrigin.REAL.value,
        }

    def _chart(self, symbol: str) -> list[dict[str, Any]]:
        cache_key = ("chart", symbol)
        hit = self._cache.get(cache_key)
        if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
            return list(hit[1])
        now = datetime.now(UTC)
        try:
            data = self._get(
                "/stock/candle",
                symbol=symbol,
                resolution="D",
                **{
                    "from": int((now - timedelta(days=365)).timestamp()),
                    "to": int(now.timestamp()),
                },
            )
        except FinnhubUnavailableError:
            data = None  # Candle access can be plan-restricted independently of quotes.
        points: dict[str, float] = {}
        if isinstance(data, dict) and data.get("s") == "ok":
            for timestamp, close in zip(
                data.get("t") or [], data.get("c") or [], strict=False
            ):
                try:
                    day = datetime.fromtimestamp(timestamp, UTC).date()
                    value = float(close)
                except (TypeError, ValueError, OverflowError, OSError):
                    continue
                if math.isfinite(value) and value > 0 and day <= now.date():
                    points[day.isoformat()] = value
        chart = [{"date": day, "close": value} for day, value in sorted(points.items())]
        if len(chart) < 2:
            chart = self._yahoo_chart(symbol)
        self._cache[cache_key] = (time.monotonic(), chart)
        return chart

    def _yahoo_chart(self, symbol: str) -> list[dict[str, Any]]:
        """Real daily closes when Finnhub candles are unavailable; never synthesize bars."""
        try:
            history = yf.Ticker(symbol).history(
                period="1y", interval="1d", auto_adjust=False, actions=False, timeout=8
            )
            if history.empty or "Close" not in history:
                return []
            points: dict[str, float] = {}
            for timestamp, close in history["Close"].items():
                day = timestamp.date()
                value = float(close)
                if (
                    math.isfinite(value)
                    and value > 0
                    and day <= datetime.now(UTC).date()
                ):
                    points[day.isoformat()] = value
            chart = [
                {"date": day, "close": value} for day, value in sorted(points.items())
            ]
            return chart if len(chart) > 1 else []
        except Exception:
            # Provider/network failures must not take down the factual snapshot or quiz.
            return []


_client: FinnhubClient | None = None


def get_finnhub() -> FinnhubClient:
    """FastAPI dependency returning a process-wide client (shared cache)."""
    global _client
    if _client is None:
        _client = FinnhubClient()
    return _client
