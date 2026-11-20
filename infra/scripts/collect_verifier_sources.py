"""Collect public brokerage PDFs into an ignored review cache (never seed blindly).

Public archival filenames are discovery hints only. PDF content must confirm
publisher, date, security, direction and horizon before a record is accepted.
"""

import argparse
import json
import re
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from pypdf import PdfReader
from pypdf.errors import PyPdfError

CACHE = Path("data/market_cache/verifier_collection")
BASE = "https://storage.googleapis.com/msi-broker-report-archive/"
ALIASES = {
    "axis_direct": "axis_securities",
    "axis_securities": "axis_securities",
    "icici_direct": "icici_securities",
    "icici_securitiess": "icici_securities",
    "motilal_oswal": "motilal_oswal",
    "motilal_oswal_securities": "motilal_oswal",
    "idbi_capital_market": "idbi_capital",
    "idbi_capital": "idbi_capital",
    "way2wealth_brokers": "way2wealth",
    "keynote_capital_ltd": "keynote_capitals",
    "kisan_ratilal_choksey_shares_and_securities": "deven_choksey",
    "kisan_ratilal_choksey_shares_and_securit": "deven_choksey",
    "kisan_ratilal_choksey_shares_and_securi": "deven_choksey",
    "asit_c__mehta": "asit_c_mehta",
    "asit_c._mehta": "asit_c_mehta",
    "emkay": "emkay",
    "emkay_global_financial_services": "emkay",
    "edelweiss_capital": "nuvama",
    "kisan_ratilal_choksey_shares_and_securitiesies": "deven_choksey",
    "krchoksey": "deven_choksey",
    "keynote_capitals_ltd": "keynote_capitals",
    "motilal_oswal_securities (2)": "motilal_oswal",
    "icici_direct (2)": "icici_securities",
    "venture": "ventura",
}


def identity(name: str) -> str:
    name = name.lower().replace(" - copy", "").strip("_ .,\u00a0")
    return ALIASES.get(name, name)


def download(record):
    path = CACHE / "pdf" / (record["key"])
    try:
        if path.exists():
            raw = path.read_bytes()
        else:
            response = requests.get(record["url"], timeout=20)
            response.raise_for_status()
            raw = response.content
            if not raw.startswith(b"%PDF") or len(raw) > 8_000_000:
                raise ValueError("Not a bounded PDF")
            path.write_bytes(raw)
        if record.get("sha256") and sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Publication digest differs from the reviewed bundle")
        cached = CACHE / "text" / (record["key"] + ".json")
        if cached.exists():
            previous = json.loads(cached.read_text(encoding="utf-8"))
            if previous.get("sha256") == sha256(raw).hexdigest():
                previous.update(record)
                cached.write_text(json.dumps(previous), encoding="utf-8")
                return {"publisher": record["publisher"], "status": "downloaded"}
        pdf = PdfReader(BytesIO(raw))
        pages = [p.extract_text() or "" for p in pdf.pages]
        result = {**record, "sha256": sha256(raw).hexdigest(), "pages": pages}
        (CACHE / "text" / (record["key"] + ".json")).write_text(
            json.dumps(result), encoding="utf-8"
        )
        return {"publisher": record["publisher"], "status": "downloaded"}
    except (requests.RequestException, PyPdfError, OSError, ValueError) as exc:
        return {
            "publisher": record["publisher"],
            "key": record["key"],
            "status": type(exc).__name__,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-bundle", action="store_true", help="Replay the shipped public corpus"
    )
    args = parser.parse_args()
    for folder in ("pdf", "text"):
        (CACHE / folder).mkdir(parents=True, exist_ok=True)
    if args.from_bundle:
        bundle = Path("data/seed/verifier/real")
        shutil.copyfile(bundle / "nse_symbols.csv", CACHE / "nse_equity.csv")
        rows = json.loads((bundle / "claims.json").read_text(encoding="utf-8"))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(download, rows))
        print(json.dumps(Counter(r["status"] for r in results)))
        if any(r["status"] != "downloaded" for r in results):
            raise RuntimeError("A reviewed publication could not be reproduced")
        return
    catalog = json.loads((CACHE / "catalog.json").read_text(encoding="utf-8"))
    choices = {}
    seen_sizes = set()
    for obj in sorted(
        catalog,
        key=lambda x: (
            (
                0
                if x["Key"].startswith("2024")
                else 1 if x["Key"].startswith("2025") else 2
            ),
            x["Key"],
        ),
    ):
        key = obj["Key"]
        match = re.fullmatch(r"(\d{8})_(.*?)_IN_(.+)\.pdf", key)
        if not match or match[1] > "20250630":
            continue
        publisher = identity(match[3])
        # Archives often index the identical sector PDF once per mentioned stock.
        # Avoid treating those copies as independent calls or wasting downloads.
        size_key = (publisher, obj["Size"])
        if size_key in seen_sizes:
            continue
        seen_sizes.add(size_key)
        group = choices.setdefault(publisher, [])
        if len(group) >= 30:
            continue
        group.append(
            {
                "publisher": publisher,
                "key": key,
                "url": BASE + quote(key),
                "archive_created_at": obj["LastModified"],
                "filename_date": match[1],
                "filename_security": match[2],
            }
        )
    selected = [r for group in choices.values() for r in group]
    for folder in ("pdf", "text"):
        (CACHE / folder).mkdir(parents=True, exist_ok=True)
    print(
        json.dumps({"selected": len(selected), "publishers": len(choices)}), flush=True
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(download, selected))
    (CACHE / "collection_results.json").write_text(
        json.dumps(results), encoding="utf-8"
    )
    print(json.dumps(Counter(r["status"] for r in results)))


if __name__ == "__main__":
    main()
