"""Daily market refresh and open-claim scoring job entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
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
from app.core.market import get_market_data_as_of, refresh_all
from app.core.models import JobRunRecord
from app.verifier.jobs import score_open_claims

_logger = get_logger("aacharya.daily_job")


def run_daily_job(
    *,
    db: Session | None = None,
    symbols: list[str] | None = None,
    refresh_fn: Callable[..., dict[str, Any]] | None = None,
    scoring_fn: Callable[[Session | None], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute market refresh + open-claim scoring and record a `job_runs` entry."""
    active_refresh = refresh_fn or refresh_all
    active_scoring = scoring_fn or score_open_claims

    refresh_summary = (
        active_refresh(symbols=symbols) if symbols is not None else active_refresh()
    )
    market_as_of = (
        str(refresh_summary.get("as_of") or get_market_data_as_of() or "") or None
    )

    scoring_summary: dict[str, Any] = {"status": "skipped", "scored": 0}
    db_recorded = False

    if db is not None:
        scoring_summary = active_scoring(db)
        status = "ok" if refresh_summary.get("status") in {"ok", "partial"} else "error"
        summary: dict[str, Any] = {
            "job_name": "daily_job",
            "status": status,
            "market_data_as_of": market_as_of,
            "market_refresh": refresh_summary,
            "claim_scoring": scoring_summary,
            "db_recorded": True,
            "ran_at": datetime.now(tz=UTC).isoformat(),
        }
        db.add(
            JobRunRecord(
                job_name="daily_job",
                status=status,
                market_data_as_of=market_as_of,
                details_json=json.dumps(summary, default=str),
            )
        )
        db.commit()
        _logger.info("daily_job_completed", extra=summary)
        return summary

    has_job_runs = False
    try:
        engine = get_engine()
        has_job_runs = inspect(engine).has_table("job_runs")
    except (SQLAlchemyError, OSError, RuntimeError) as exc:
        _logger.warning("daily_job_db_unavailable", extra={"error": str(exc)})

    if has_job_runs:
        with get_session_factory()() as session:
            scoring_summary = active_scoring(session)
            status = (
                "ok" if refresh_summary.get("status") in {"ok", "partial"} else "error"
            )
            summary = {
                "job_name": "daily_job",
                "status": status,
                "market_data_as_of": market_as_of,
                "market_refresh": refresh_summary,
                "claim_scoring": scoring_summary,
                "db_recorded": True,
                "ran_at": datetime.now(tz=UTC).isoformat(),
            }
            session.add(
                JobRunRecord(
                    job_name="daily_job",
                    status=status,
                    market_data_as_of=market_as_of,
                    details_json=json.dumps(summary, default=str),
                )
            )
            session.commit()
            db_recorded = True
            _logger.info("daily_job_completed", extra=summary)
            return summary

    scoring_summary = active_scoring(None)
    status = "ok" if refresh_summary.get("status") in {"ok", "partial"} else "error"
    summary = {
        "job_name": "daily_job",
        "status": status,
        "market_data_as_of": market_as_of,
        "market_refresh": refresh_summary,
        "claim_scoring": scoring_summary,
        "db_recorded": db_recorded,
        "ran_at": datetime.now(tz=UTC).isoformat(),
    }
    _logger.info("daily_job_completed", extra=summary)
    return summary


def main() -> int:
    """CLI entrypoint for `infra/scripts/daily_job.py`."""
    parser = argparse.ArgumentParser(
        description="Run Aacharya daily market & claim job."
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="Optional subset of NSE symbols to refresh.",
    )
    args = parser.parse_args()
    summary = run_daily_job(symbols=args.symbols)
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
