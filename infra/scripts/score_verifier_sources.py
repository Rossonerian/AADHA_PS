"""Score reviewed candidate PDFs through core.market and the existing Verifier policy.

All failures stay in the ledger; selection is chronological, never by outcome.
Price downloads use a separate ignored cache, not the platform's tracked prices.
"""

import json
import os
import shutil
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path("data/market_cache/verifier_collection")
os.environ["MARKET_DATA_DIR"] = str((ROOT / "market").resolve())

from app.core import market
from app.verifier.schemas import Direction
from app.verifier.scoring import evaluate_claim


def main():
    for name in ("nse_symbols.csv", "symbol_aliases.json"):
        target = ROOT / "market" / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path("data/seed/market") / name, target)
    candidates = json.loads((ROOT / "candidates.json").read_text(encoding="utf-8"))
    cohort_path = Path("data/seed/verifier/real/cohort.json")
    if cohort_path.exists():
        cohort = json.loads(cohort_path.read_text(encoding="utf-8"))["publications"]
        identities = {(r["url"], r["sha256"], r["publisher"]) for r in cohort}
        candidates = [
            r
            for r in candidates
            if (r["url"], r["sha256"], r["publisher"]) in identities
        ]
        if len(candidates) != len(cohort):
            raise ValueError(
                "A frozen publication no longer has unambiguous source evidence"
            )
    by_pub = defaultdict(list)
    for row in sorted(candidates, key=lambda r: (r["report_date"], r["sha256"])):
        by_pub[row["publisher"]].append(row)
    # Extra chronological candidates cover missing prices without choosing winners.
    selected = [row for group in by_pub.values() for row in group[:10]]
    requirements = defaultdict(list)
    for row in selected:
        requirements[row["symbol"]].append(row)
    frames = {}

    def fetch(item):
        symbol, rows = item
        start = min(date.fromisoformat(r["report_date"]) for r in rows)
        end = max(
            date.fromisoformat(r["report_date"])
            + timedelta(days=r["window_days"] * 2 + 35)
            for r in rows
        )
        end = min(end, date(2026, 11, 20))
        try:
            f = market.prices(symbol, start, end)
            if not f.empty and (f.data_origin != "real").any():
                raise ValueError("Non-real price data")
            return symbol, f
        except (requests.RequestException, OSError, RuntimeError, ValueError):
            return symbol, pd.DataFrame()

    first = min(date.fromisoformat(r["report_date"]) for r in selected)
    benchmark = market.index("NIFTY50", first, date(2026, 11, 20))
    assert not benchmark.empty and set(benchmark.data_origin) == {"real"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for symbol, frame in pool.map(fetch, requirements.items()):
            frames[symbol] = frame
            print(json.dumps({"symbol": symbol, "price_rows": len(frame)}), flush=True)
    scored, rejected = [], []
    counts = Counter()
    logical_seen = set()
    for row in selected:
        identity = row["publisher"], row["symbol"], row["report_date"]
        if identity in logical_seen:
            rejected.append(
                {"key": row["key"], "reason": "duplicate_publisher_security_date"}
            )
            continue
        logical_seen.add(identity)
        if counts[row["publisher"]] >= 5:
            continue
        frame = frames[row["symbol"]]
        result = evaluate_claim(
            direction=Direction(row["direction"]),
            start=date.fromisoformat(row["report_date"]),
            window_days=row["window_days"],
            stock=frame,
            benchmark=benchmark,
            target=row["target"],
        )
        if result is None or result.correct is None:
            rejected.append(
                {"key": row["key"], "reason": "missing_or_ambiguous_adjusted_prices"}
            )
            continue
        counts[row["publisher"]] += 1
        scored.append(
            {
                **row,
                "outcome": {
                    **asdict(result),
                    "window_end": str(result.window_end),
                    "data_origin": "real",
                },
            }
        )
    (ROOT / "scored.json").write_text(json.dumps(scored, indent=2), encoding="utf-8")
    (ROOT / "scoring_rejections.json").write_text(
        json.dumps(rejected, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "scored_claims": len(scored),
                "counts": counts,
                "qualifying_sources": sum(n >= 5 for n in counts.values()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
