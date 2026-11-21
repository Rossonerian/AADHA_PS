"""Exercise real-history provider failover without external requests."""

from unittest.mock import Mock

import pandas as pd
import pytest

from app.core import finnhub


@pytest.mark.parametrize(
    "response", [None, {"s": "no_data"}, {"s": "ok", "t": [], "c": []}]
)
def test_missing_candles_use_yahoo_and_cache(monkeypatch, response):
    client = finnhub.FinnhubClient("test")
    monkeypatch.setattr(client, "_get", lambda *args, **kwargs: response)
    history = pd.DataFrame(
        {"Close": [600.0, float("nan"), -1.0, 610.0, float("inf")]},
        index=pd.date_range("2025-01-01", periods=5, tz="America/New_York"),
    )
    ticker = Mock()
    ticker.history.return_value = history
    factory = Mock(return_value=ticker)
    monkeypatch.setattr(finnhub.yf, "Ticker", factory)
    expected = [
        {"date": "2025-01-01", "close": 600.0},
        {"date": "2025-01-04", "close": 610.0},
    ]
    assert client._chart("QQQ") == expected
    assert client._chart("QQQ") == expected
    factory.assert_called_once_with("QQQ")
    ticker.history.assert_called_once_with(
        period="1y", interval="1d", auto_adjust=False, actions=False, timeout=8
    )


def test_plan_restriction_uses_benchmark_proxy(monkeypatch):
    client = finnhub.FinnhubClient("test")

    def restricted(*args, **kwargs):
        raise finnhub.FinnhubUnavailableError("Plan restricted")

    monkeypatch.setattr(client, "_get", restricted)
    fallback = Mock(
        return_value=[
            {"date": "2025-01-01", "close": 600.0},
            {"date": "2025-01-02", "close": 610.0},
        ]
    )
    monkeypatch.setattr(client, "_yahoo_chart", fallback)
    display, symbol = finnhub.normalize_symbol("NDX")
    assert display == "NDX"
    assert len(client._chart(symbol)) == 2
    fallback.assert_called_once_with("QQQ")


def test_valid_finnhub_history_does_not_fetch_yahoo(monkeypatch):
    client = finnhub.FinnhubClient("test")
    monkeypatch.setattr(
        client,
        "_get",
        lambda *args, **kwargs: {
            "s": "ok",
            "t": [1700000000, 1700086400],
            "c": [180, 190],
        },
    )
    fallback = Mock(side_effect=AssertionError("Unexpected fallback"))
    monkeypatch.setattr(client, "_yahoo_chart", fallback)
    assert len(client._chart("AAPL")) == 2
    fallback.assert_not_called()


@pytest.mark.parametrize(
    "history",
    [
        pd.DataFrame(),
        pd.DataFrame({"Close": [100]}, index=pd.date_range("2025-01-01", periods=1)),
    ],
)
def test_insufficient_yahoo_history_stays_empty(monkeypatch, history):
    ticker = Mock()
    ticker.history.return_value = history
    monkeypatch.setattr(finnhub.yf, "Ticker", lambda symbol: ticker)
    assert finnhub.FinnhubClient("test")._yahoo_chart("AAPL") == []


def test_yahoo_failure_is_nonfatal(monkeypatch):
    ticker = Mock()
    ticker.history.side_effect = TimeoutError("Provider unavailable")
    monkeypatch.setattr(finnhub.yf, "Ticker", lambda symbol: ticker)
    assert finnhub.FinnhubClient("test")._yahoo_chart("AAPL") == []
