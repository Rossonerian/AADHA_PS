"""Export reviewed claims with immutable core.market evidence, or load the bundle.

Run with PYTHONPATH=services/api. Export never writes the database; --load does.
"""

import argparse
import json
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pandas as pd
import requests
from app.core.config import get_settings
from app.verifier.real_seed import load_bundle, validate_bundle
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

CACHE = Path("data/market_cache/verifier_collection")
DESTINATION = Path("data/seed/verifier/real")


def export() -> None:
    rows = json.loads((CACHE / "scored.json").read_text(encoding="utf-8"))
    counts = Counter(row["publisher"] for row in rows)
    rows = [row for row in rows if counts[row["publisher"]] >= 5]
    if len({row["publisher"] for row in rows}) < 30:
        raise ValueError(
            "Keep the real-data gate open: fewer than 30 qualified sources"
        )
    prices = DESTINATION / "prices"
    prices.mkdir(parents=True, exist_ok=True)
    digests = {}
    for symbol in sorted({row["symbol"] for row in rows} | {"NIFTY50"}):
        source = CACHE / "market" / "prices" / f"{symbol}.csv"
        target = prices / source.name
        shutil.copyfile(source, target)
        digests[symbol] = sha256(target.read_bytes()).hexdigest()
    for row in rows:
        row["price_sha256"] = digests[row["symbol"]]
        row["benchmark_sha256"] = digests["NIFTY50"]
        row["retrieved_on"] = "2026-11-21"
        row["scoring_cutoff"] = "2026-11-20"
    symbols = pd.read_csv(CACHE / "nse_equity.csv")
    symbols = symbols.loc[symbols.SYMBOL.isin({row["symbol"] for row in rows})].copy()
    symbols["data_origin"] = "real"
    symbols["source"] = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    symbols["observed_on"] = "2026-11-21"
    symbols.to_csv(DESTINATION / "nse_symbols.csv", index=False)
    (DESTINATION / "claims.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    validate_bundle(DESTINATION)
    print(
        json.dumps(
            {
                "status": "exported",
                "sources": len(counts),
                "qualified_sources": len({r["publisher"] for r in rows}),
                "scored_claims": len(rows),
                "price_files": len(digests),
            }
        )
    )


def check_publications() -> None:
    """Check the actual public PDF bytes against the reviewed document digests."""
    rows = json.loads((DESTINATION / "claims.json").read_text(encoding="utf-8"))

    def check(row):
        response = requests.get(row["url"], timeout=30)
        response.raise_for_status()
        matched = (
            response.content.startswith(b"%PDF")
            and sha256(response.content).hexdigest() == row["sha256"]
        )
        if not matched:
            raise ValueError(
                f"Publication changed or is not a PDF: {row['publisher']}/{row['key']}"
            )
        return {
            "publisher": row["publisher"],
            "url": row["url"],
            "sha256": row["sha256"],
            "http_status": response.status_code,
            "digest_match": True,
            "data_origin": "real",
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(check, rows))
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "data_origin": "real",
        "publications": receipts,
    }
    path = Path("docs/evidence/real_source_publications.json")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"public_pdfs_verified": len(receipts), "digest_matches": len(receipts)}
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--check-publications", action="store_true")
    args = parser.parse_args()
    if args.export:
        export()
    if args.check_publications:
        check_publications()
    if args.load:
        settings = get_settings()
        engine = create_engine(settings.database_url_unpooled or settings.database_url)
        try:
            print(json.dumps(load_bundle(sessionmaker(engine), DESTINATION)))
        finally:
            engine.dispose()
    if not args.export and not args.load and not args.check_publications:
        result = validate_bundle(DESTINATION)
        print(json.dumps({"status": "validated", "claims": len(result)}))


if __name__ == "__main__":
    main()
