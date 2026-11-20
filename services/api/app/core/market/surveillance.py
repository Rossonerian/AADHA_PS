"""NSE ASM/GSM market surveillance lookup."""

from __future__ import annotations

import csv
from datetime import date as DateType

from app.core.market.prices import parse_market_date
from app.core.market.symbols import canonicalize_ticker, get_market_data_dir


def surveillance(
    symbol: str,
    date: DateType | str | None = None,
) -> str | None:
    """Return active ASM/GSM surveillance stage for `symbol` on `date`, or `None`."""
    if not symbol or not symbol.strip():
        return None

    norm_symbol = canonicalize_ticker(symbol)
    csv_path = get_market_data_dir() / "surveillance_list.csv"
    if not csv_path.exists():
        return None

    rows: list[dict[str, str]] = []
    latest_as_of: DateType | None = None

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
            raw_as_of = (row.get("as_of_date") or "").strip()
            if raw_as_of:
                parsed_as_of = parse_market_date(raw_as_of)
                if latest_as_of is None or parsed_as_of > latest_as_of:
                    latest_as_of = parsed_as_of

    if date is not None:
        target_date = parse_market_date(date)
    elif latest_as_of is not None:
        target_date = latest_as_of
    else:
        target_date = DateType.today()

    matches: list[tuple[DateType, str]] = []
    for row in rows:
        row_sym = (row.get("symbol") or "").strip().upper()
        if row_sym != norm_symbol:
            continue

        raw_from = (row.get("effective_from") or "").strip()
        if not raw_from:
            continue
        eff_from = parse_market_date(raw_from)

        raw_to = (row.get("effective_to") or "").strip()
        eff_to = parse_market_date(raw_to) if raw_to else None

        if eff_from <= target_date and (eff_to is None or target_date <= eff_to):
            stage = (row.get("stage") or "").strip()
            if stage:
                matches.append((eff_from, stage))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]
