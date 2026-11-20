"""Rebuild Education price fields from the adjusted `core.market` interface.

Unavailable or incomplete history remains synthetic. The script never promotes a
record based on cached seed values alone.

Usage from the repository root:
    PYTHONPATH=services/api python -m app.education.scripts.refresh_market_data
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from ...core import market
from .. import explain as explain_module
from ..exceptions import ValidationDomainError
from ..scenarios import recompute_scenario_outcome

REPO_ROOT = Path(__file__).resolve().parents[5]
MARKET_SEED = REPO_ROOT / "data" / "seed" / "market"
EDUCATION_SEED = REPO_ROOT / "data" / "seed" / "education"


def _read_yaml(path: Path, key: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return document, document.get(key, [])


def _write_yaml(path: Path, document: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def refresh_scenarios() -> tuple[int, list[str]]:
    path = EDUCATION_SEED / "scenarios.yaml"
    document, scenarios = _read_yaml(path, "scenarios")
    refreshed = 0
    unavailable: list[str] = []
    for scenario in scenarios:
        try:
            outcome = recompute_scenario_outcome(
                scenario["symbol"],
                scenario["as_of_date"],
                int(scenario["window_days"]),
            )
        except ValidationDomainError as exc:
            if exc.code != "MARKET_DATA_MISSING":
                raise
            scenario["data_origin"] = "synthetic"
            unavailable.append(scenario["id"])
            continue

        if outcome["data_origin"] != "real":
            scenario["data_origin"] = "synthetic"
            unavailable.append(scenario["id"])
            continue

        chart_start = date.fromisoformat(scenario["as_of_date"]) - timedelta(days=60)
        chart_rows = market.prices(
            scenario["symbol"], chart_start, scenario["as_of_date"]
        )
        chart_rows = chart_rows[
            chart_rows["date"] <= pd.Timestamp(scenario["as_of_date"])
        ]
        if (
            chart_rows.empty
            or "data_origin" not in chart_rows.columns
            or set(chart_rows["data_origin"].dropna().astype(str).str.lower())
            != {"real"}
        ):
            scenario["data_origin"] = "synthetic"
            unavailable.append(scenario["id"])
            continue
        chart_rows = chart_rows.tail(30)

        scenario["outcome"] = {
            key: value for key, value in outcome.items() if key != "data_origin"
        }
        scenario["context"]["chart"] = [
            {
                "date": row["date"].date().isoformat(),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
            }
            for _, row in chart_rows.iterrows()
        ]
        scenario["data_origin"] = "real"
        refreshed += 1

    _write_yaml(path, document)
    return refreshed, unavailable


def refresh_explain_records() -> tuple[int, list[str]]:
    path = EDUCATION_SEED / "explain_stocks.yaml"
    document, records = _read_yaml(path, "explain_stocks")
    refreshed = 0
    unavailable: list[str] = []
    for record in records:
        rebuilt = explain_module._real_explain_series(record, record["moves"])
        if rebuilt is None:
            record["data_origin"] = "synthetic"
            unavailable.append(f"{record['symbol']}:{record['year']}")
            continue
        record["chart"], record["moves"] = rebuilt
        record["data_origin"] = "real"
        refreshed += 1

    _write_yaml(path, document)
    return refreshed, unavailable


def main() -> None:
    previous_market_dir = os.environ.get("MARKET_DATA_DIR")
    previous_app_env = os.environ.get("APP_ENV")
    with tempfile.TemporaryDirectory(
        prefix="education-market-", dir=REPO_ROOT / "work"
    ) as temp_root:
        market_dir = Path(temp_root) / "market"
        shutil.copytree(MARKET_SEED, market_dir)
        os.environ["MARKET_DATA_DIR"] = str(market_dir)
        os.environ["APP_ENV"] = "development"
        try:
            scenarios_count, missing_scenarios = refresh_scenarios()
            explain_count, missing_explain = refresh_explain_records()
        finally:
            if previous_market_dir is None:
                os.environ.pop("MARKET_DATA_DIR", None)
            else:
                os.environ["MARKET_DATA_DIR"] = previous_market_dir
            if previous_app_env is None:
                os.environ.pop("APP_ENV", None)
            else:
                os.environ["APP_ENV"] = previous_app_env

    print(
        f"Scenarios with complete adjusted real series: {scenarios_count}/24; "
        f"synthetic/unavailable: {', '.join(missing_scenarios) or 'none'}"
    )
    print(
        f"Explain records with complete adjusted real series: {explain_count}/30; "
        f"synthetic/unavailable: {', '.join(missing_explain) or 'none'}"
    )


if __name__ == "__main__":
    main()
