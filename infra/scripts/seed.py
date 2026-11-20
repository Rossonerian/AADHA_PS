"""Idempotent seed data validator and database seed marker for `data/seed/`."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.core.db import get_engine, get_session_factory
from app.core.logging import get_logger
from app.core.market import get_market_data_as_of
from app.core.models import JobRunRecord

_logger = get_logger("aacharya.seed")

VALID_DATA_ORIGINS = frozenset({"real", "synthetic"})

REQUIRED_PRICE_COLUMNS = frozenset(
    {
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
    }
)


def _validate_csv_file(csv_path: Path, seed_root: Path) -> tuple[int, set[str]]:
    rel = csv_path.relative_to(seed_root).as_posix()
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV file has no header row: {rel}")
        fieldnames = set(reader.fieldnames)

        if "data_origin" not in fieldnames:
            raise ValueError(f"CSV missing `data_origin` column: {rel}")

        if rel.startswith("market/prices/"):
            missing = REQUIRED_PRICE_COLUMNS - fieldnames
            if missing:
                raise ValueError(f"Price CSV {rel} missing columns: {sorted(missing)}")
        elif rel == "market/nse_symbols.csv":
            required = {
                "symbol",
                "company_name",
                "series",
                "data_origin",
                "source",
                "as_of_date",
            }
            missing = required - fieldnames
            if missing:
                raise ValueError(f"{rel} missing columns: {sorted(missing)}")
        elif rel == "market/surveillance_list.csv":
            required = {"symbol", "list_type", "stage", "effective_from", "data_origin"}
            missing = required - fieldnames
            if missing:
                raise ValueError(f"{rel} missing columns: {sorted(missing)}")
        elif rel == "market/sebi_ra_ia.csv":
            required = {"reg_no", "type", "name", "status", "data_origin"}
            missing = required - fieldnames
            if missing:
                raise ValueError(f"{rel} missing columns: {sorted(missing)}")

        count = 0
        origins: set[str] = set()
        for idx, row in enumerate(reader, start=1):
            origin = (row.get("data_origin") or "").strip().lower()
            if origin not in VALID_DATA_ORIGINS:
                raise ValueError(
                    f"Invalid or missing data_origin={origin!r} in {rel} row {idx}"
                )
            origins.add(origin)
            count += 1

        if count == 0:
            raise ValueError(f"CSV file contains zero data rows: {rel}")
        return count, origins


def _validate_json_file(json_path: Path, seed_root: Path) -> tuple[int, set[str]]:
    rel = json_path.relative_to(seed_root).as_posix()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    origins: set[str] = set()

    if rel == "market/manifest.json":
        if not isinstance(payload, dict):
            raise TypeError(f"{rel} must be a JSON object")
        origin = str(payload.get("data_origin") or "").strip().lower()
        if origin not in VALID_DATA_ORIGINS:
            raise ValueError(f"Invalid data_origin={origin!r} in {rel}")
        origins.add(origin)
        return 1, origins

    if rel == "market/symbol_aliases.json":
        if not isinstance(payload, dict):
            raise TypeError(f"{rel} must be a JSON object")
        origin = str(payload.get("data_origin") or "").strip().lower()
        if origin not in VALID_DATA_ORIGINS:
            raise ValueError(f"Invalid data_origin={origin!r} in {rel}")
        aliases = payload.get("aliases")
        if not isinstance(aliases, dict) or not aliases:
            raise ValueError(f"{rel} must contain a non-empty `aliases` dictionary")
        origins.add(origin)
        return len(aliases), origins

    if isinstance(payload, list):
        for idx, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise TypeError(f"{rel} item {idx} must be a JSON object")
            origin = str(item.get("data_origin") or "").strip().lower()
            if origin not in VALID_DATA_ORIGINS:
                raise ValueError(f"Invalid data_origin={origin!r} in {rel} item {idx}")
            origins.add(origin)
        return len(payload), origins

    if isinstance(payload, dict):
        top_origin = payload.get("data_origin")
        if (
            isinstance(top_origin, str)
            and top_origin.strip().lower() in VALID_DATA_ORIGINS
        ):
            origins.add(top_origin.strip().lower())
            return 1, origins
        record_count = 0
        for key, value in payload.items():
            if isinstance(value, list):
                for idx, item in enumerate(value, start=1):
                    if not isinstance(item, dict):
                        raise TypeError(f"{rel}[{key}][{idx}] must be a JSON object")
                    origin = str(item.get("data_origin") or "").strip().lower()
                    if origin not in VALID_DATA_ORIGINS:
                        raise ValueError(
                            f"Invalid data_origin={origin!r} in {rel}[{key}][{idx}]"
                        )
                    origins.add(origin)
                    record_count += 1
        if record_count > 0:
            return record_count, origins
        raise ValueError(f"JSON file missing valid `data_origin`: {rel}")

    raise TypeError(f"Unsupported JSON payload in {rel}")


def _record_seed_job_run(
    summary: dict[str, Any],
    *,
    db: Session | None = None,
) -> bool:
    if db is not None:
        db.add(
            JobRunRecord(
                job_name="seed",
                status="ok",
                market_data_as_of=summary.get("market_data_as_of"),
                details_json=json.dumps(summary, default=str),
            )
        )
        db.commit()
        return True

    try:
        engine = get_engine()
        if not inspect(engine).has_table("job_runs"):
            _logger.info("seed_job_run_skipped_no_table")
            return False
        with get_session_factory()() as session:
            session.add(
                JobRunRecord(
                    job_name="seed",
                    status="ok",
                    market_data_as_of=summary.get("market_data_as_of"),
                    details_json=json.dumps(summary, default=str),
                )
            )
            session.commit()
        return True
    except (SQLAlchemyError, OSError, RuntimeError) as exc:
        _logger.warning("seed_job_run_db_skipped", extra={"error": str(exc)})
        return False


def seed(
    seed_dir: Path | None = None,
    *,
    db: Session | None = None,
) -> dict[str, Any]:
    """Validate all seed files under `data/seed/` and record a seed run if DB is ready."""
    resolved_seed_dir = (seed_dir or (REPO_ROOT / "data" / "seed")).resolve()
    if not resolved_seed_dir.exists():
        raise FileNotFoundError(f"Seed directory not found: {resolved_seed_dir}")

    files_validated = 0
    records_validated = 0
    all_origins: set[str] = set()
    subdirs_seen: set[str] = set()

    for subdir_name in ("market", "education", "verifier"):
        subdir = resolved_seed_dir / subdir_name
        if not subdir.exists():
            continue
        subdirs_seen.add(subdir_name)

        for file_path in sorted(subdir.rglob("*")):
            if file_path.is_dir() or file_path.name.startswith("."):
                continue
            suffix = file_path.suffix.lower()
            if suffix == ".csv":
                count, origins = _validate_csv_file(file_path, resolved_seed_dir)
            elif suffix == ".json":
                count, origins = _validate_json_file(file_path, resolved_seed_dir)
            else:
                continue
            files_validated += 1
            records_validated += count
            all_origins.update(origins)

    if files_validated == 0:
        raise ValueError(f"No seed files found under {resolved_seed_dir}")

    market_as_of = get_market_data_as_of()
    summary: dict[str, Any] = {
        "status": "ok",
        "seed_dir": str(resolved_seed_dir),
        "subdirs": sorted(subdirs_seen),
        "files_validated": files_validated,
        "records_validated": records_validated,
        "data_origins": sorted(all_origins),
        "market_data_as_of": market_as_of,
    }

    db_recorded = _record_seed_job_run(summary, db=db)
    summary["db_recorded"] = db_recorded
    _logger.info("seed_completed", extra=summary)
    return summary


def main() -> int:
    """CLI entrypoint for `infra/scripts/seed.py`."""
    parser = argparse.ArgumentParser(description="Validate and seed Aacharya datasets.")
    parser.add_argument(
        "--seed-dir",
        type=Path,
        default=None,
        help="Optional override for data/seed directory.",
    )
    args = parser.parse_args()
    summary = seed(seed_dir=args.seed_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
