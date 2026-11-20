"""Test helper: serve Education's seeded price series through the real core.market API.

`app.core.market` reads OHLCV from `<MARKET_DATA_DIR>/prices/<SYMBOL>.csv` and never
hits the network when APP_ENV=test. Education scenarios and explain fixtures were
generated from `tests/education/fixtures/market_prices_seed.json`, so tests copy the
configured market directory to a temp dir, write those series as CSV cache files,
and point MARKET_DATA_DIR at it until cleanup.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from app.core.market.symbols import canonicalize_ticker, get_market_data_dir

PRICE_SEED_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "market_prices_seed.json"
)
_CSV_FIELDS = ["date", "open", "high", "low", "close", "volume"]


def use_education_price_seed() -> Callable[[], None]:
    """Install the Education price seed as the market cache; return a cleanup callable."""
    source_dir = get_market_data_dir()
    tmp_root = Path(tempfile.mkdtemp(prefix="edu_market_"))
    market_dir = tmp_root / "market"
    shutil.copytree(source_dir, market_dir)
    prices_dir = market_dir / "prices"
    prices_dir.mkdir(parents=True, exist_ok=True)

    previous = os.environ.get("MARKET_DATA_DIR")
    os.environ["MARKET_DATA_DIR"] = str(market_dir)

    payload = json.loads(PRICE_SEED_PATH.read_text(encoding="utf-8"))
    for symbol, rows in payload.items():
        if not isinstance(rows, list):
            continue  # e.g. top-level "data_origin" marker
        names = {symbol}
        if symbol != "NIFTY50":
            names.add(canonicalize_ticker(symbol) or symbol)
        for name in names:
            with (prices_dir / f"{name}.csv").open(
                "w", newline="", encoding="utf-8"
            ) as fh:
                writer = csv.DictWriter(
                    fh, fieldnames=_CSV_FIELDS, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(rows)

    def cleanup() -> None:
        if previous is None:
            os.environ.pop("MARKET_DATA_DIR", None)
        else:
            os.environ["MARKET_DATA_DIR"] = previous
        shutil.rmtree(tmp_root, ignore_errors=True)

    return cleanup
