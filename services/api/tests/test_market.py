"""Tests for `app.core.market` (prices, indices, symbols, surveillance, SEBI, health)."""

from __future__ import annotations

from datetime import date as DateType
from pathlib import Path

import pandas as pd
import pytest
import yfinance as yf
from fastapi.testclient import TestClient

from app.core.market import (
    get_market_data_as_of,
    index,
    prices,
    resolve_symbol,
    sebi_registered,
    surveillance,
)


def test_prices_reliance_from_real_cache() -> None:
    """`prices('RELIANCE', ...)` returns real adjusted daily OHLCV with canonical columns."""
    df = prices("RELIANCE", "2024-01-01", "2024-06-30")
    assert not df.empty
    assert list(df.columns) == [
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
    assert (df["data_origin"] == "real").all()
    assert (df["symbol"] == "RELIANCE").all()
    assert (df["close"] > 0).all()
    assert df["date"].min().date() >= DateType(2024, 1, 1)
    assert df["date"].max().date() <= DateType(2024, 6, 30)


def test_prices_normalizes_suffix_and_aliases() -> None:
    """`prices` handles `.NS`, `$` prefix, and renamed corporate aliases (`ZOMATO` -> `ETERNAL`)."""
    ns_df = prices("$INFY.NS", "2024-01-01", "2024-02-15")
    assert not ns_df.empty
    assert (ns_df["symbol"] == "INFY").all()

    zomato_df = prices("ZOMATO", "2024-01-01", "2024-02-15")
    assert not zomato_df.empty
    assert (zomato_df["symbol"] == "ETERNAL").all()


def test_prices_offline_fallback_to_cache_when_yfinance_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `yfinance` fails on an extended range, `prices` falls back to cached data."""
    market_dir = tmp_path / "market"
    prices_dir = market_dir / "prices"
    prices_dir.mkdir(parents=True)

    pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.5],
            "volume": [1000, 1200],
            "symbol": ["RELIANCE", "RELIANCE"],
            "source": ["yfinance:NSE_adjusted", "yfinance:NSE_adjusted"],
            "as_of_date": ["2024-01-03", "2024-01-03"],
            "data_origin": ["real", "real"],
        }
    ).to_csv(prices_dir / "RELIANCE.csv", index=False)

    monkeypatch.setenv("MARKET_DATA_DIR", str(market_dir))

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("Simulated Yahoo Finance outage")

    monkeypatch.setattr(yf, "Ticker", _boom)

    df = prices("RELIANCE", "2024-01-01", "2024-02-01", allow_live=True)
    assert len(df) == 2
    assert (df["data_origin"] == "real").all()


def test_index_nifty50_and_sensex() -> None:
    """`index` returns real OHLCV DataFrames for NIFTY50 and SENSEX and rejects unknowns."""
    nifty = index("NIFTY50", "2024-01-01", "2024-03-31")
    assert not nifty.empty
    assert (nifty["symbol"] == "NIFTY50").all()
    assert (nifty["data_origin"] == "real").all()

    sensex = index("BSE SENSEX", "2024-01-01", "2024-03-31")
    assert not sensex.empty
    assert (sensex["symbol"] == "SENSEX").all()
    assert (sensex["data_origin"] == "real").all()

    with pytest.raises(ValueError, match="Unknown benchmark index"):
        index("FOOBAR100", "2024-01-01", "2024-03-31")


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("RELIANCE", "RELIANCE"),
        ("$TCS", "TCS"),
        ("INFY.NS", "INFY"),
        ("Buy $RELIANCE before earnings", "RELIANCE"),
        ("RIL", "RELIANCE"),
        ("Infy", "INFY"),
        ("HDFC Bank", "HDFCBANK"),
        ("SBI Q2 profit", "SBIN"),
        ("Zomato delivery growth", "ETERNAL"),
        ("Tata Motors EV sales", "TMPV"),
        ("L&T order book", "LT"),
        ("DMart", "DMART"),
        ("Yes Bank recovery", "YESBANK"),
        ("Vodafone Idea debt", "IDEA"),
        ("Suzlon Enrgy Limited", "SUZLON"),
        ("Avenue Supermrts", "DMART"),
        ("Yes, this is a good idea", None),
        ("No tips here", None),
        ("Best free market news update today", None),
        ("All good for now, high profit target", None),
        ("", None),
    ],
)
def test_resolve_symbol_matches_and_stopword_guards(
    raw_text: str,
    expected: str | None,
) -> None:
    """`resolve_symbol` handles tickers, aliases, fuzzy names, and avoids traps."""
    assert resolve_symbol(raw_text) == expected


def test_surveillance_lookup() -> None:
    """`surveillance` returns active ASM stage during effective window and None outside."""
    assert surveillance("SUZLON", "2023-10-15") == "ASM-LT-Stage-IV"
    assert surveillance("SUZLON.NS", DateType(2023, 10, 3)) == "ASM-LT-Stage-IV"
    assert surveillance("COCHINSHIP", "2024-08-15") == "ASM-LT-Stage-I"
    assert surveillance("RVNL", "2024-09-01") == "ASM-ST-Stage-I"
    assert surveillance("TCS", "2024-06-01") is None
    assert surveillance("SUZLON", "2026-11-20") is None


def test_sebi_registered_lookup() -> None:
    """`sebi_registered` verifies real RA/IA numbers and names and rejects unknowns."""
    ra = sebi_registered("INH000000412")
    assert ra == {"found": True, "type": "RA", "reg_no": "INH000000412"}

    ia = sebi_registered("INA200005166")
    assert ia == {"found": True, "type": "IA", "reg_no": "INA200005166"}

    by_name = sebi_registered("Motilal Oswal")
    assert by_name == {"found": True, "type": "RA", "reg_no": "INH000000412"}

    assert sebi_registered("INH999999999") == {
        "found": False,
        "type": None,
        "reg_no": None,
    }
    assert sebi_registered("Finfluencer Guarantee Tips Club") == {
        "found": False,
        "type": None,
        "reg_no": None,
    }
    assert sebi_registered("Securities Ltd") == {
        "found": False,
        "type": None,
        "reg_no": None,
    }


def test_health_reflects_real_market_data_as_of(client: TestClient) -> None:
    """`/api/v1/health` surfaces non-null `market_data_as_of` matching `manifest.json`."""
    expected = get_market_data_as_of()
    assert expected is not None
    DateType.fromisoformat(expected)

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["db"] == "ok"
    assert payload["market_data_as_of"] == expected
