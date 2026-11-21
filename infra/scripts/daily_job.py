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

_logger = get_logger("paisaproof.daily_job")


def _error_summary(exc: BaseException) -> dict[str, Any]:
    return {"status": "error", "type": type(exc).__name__, "error": str(exc)[:500]}


def _record_run(session: Session, summary: dict[str, Any]) -> None:
    try:
        session.add(
            JobRunRecord(
                job_name="daily_job",
                status=summary["status"],
                market_data_as_of=summary["market_data_as_of"],
                details_json=json.dumps(summary, default=str),
            )
        )
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise


def _execute(
    session: Session | None,
    *,
    symbols: list[str] | None,
    active_refresh: Callable[..., dict[str, Any]],
    active_scoring: Callable[[Session | None], dict[str, Any]],
) -> dict[str, Any]:
    """Run refresh then scoring; never raises, always returns a summary."""
    try:
        refresh_summary = (
            active_refresh(symbols=symbols) if symbols is not None else active_refresh()
        )
    except Exception as exc:
        _logger.exception("daily_job_refresh_failed")
        refresh_summary = _error_summary(exc)
    refresh_ok = refresh_summary.get("status") in {"ok", "partial"}
    try:
        market_as_of = (
            str(refresh_summary.get("as_of") or get_market_data_as_of() or "") or None
        )
    except Exception:  # noqa: BLE001
        market_as_of = None

    scoring_summary: dict[str, Any] = {"status": "skipped", "scored": 0}
    if not refresh_ok:
        # Scoring against stale or missing bars would produce wrong outcomes.
        scoring_summary = {
            "status": "skipped",
            "scored": 0,
            "reason": "market_refresh_failed",
        }
    else:
        try:
            scoring_summary = active_scoring(session)
        except Exception as exc:
            _logger.exception("daily_job_scoring_failed")
            if session is not None:
                session.rollback()
            scoring_summary = {**_error_summary(exc), "scored": 0}

    if not refresh_ok or scoring_summary.get("status") == "error":
        status = "failed"
    elif refresh_summary.get("status") == "partial" or scoring_summary.get("failed"):
        status = "degraded"
    else:
        status = "ok"
    return {
        "job_name": "daily_job",
        "status": status,
        "market_data_as_of": market_as_of,
        "market_refresh": refresh_summary,
        "claim_scoring": scoring_summary,
        "db_recorded": False,
        "ran_at": datetime.now(tz=UTC).isoformat(),
    }


def run_daily_job(
    *,
    db: Session | None = None,
    symbols: list[str] | None = None,
    refresh_fn: Callable[..., dict[str, Any]] | None = None,
    scoring_fn: Callable[[Session | None], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute market refresh + open-claim scoring and always record a `job_runs` entry.

    Failures (refresh error, scoring exception) are captured in the summary with
    status `failed`; scoring is skipped when the market refresh failed.
    """
    kwargs: dict[str, Any] = {
        "symbols": symbols,
        "active_refresh": refresh_fn or refresh_all,
        "active_scoring": scoring_fn or score_open_claims,
    }
    if db is not None:
        summary = _execute(db, **kwargs)
        summary["db_recorded"] = True
        _record_run(db, summary)
        _logger.info("daily_job_completed", extra=summary)
        return summary

    has_job_runs = False
    try:
        has_job_runs = inspect(get_engine()).has_table("job_runs")
    except (SQLAlchemyError, OSError, RuntimeError) as exc:
        _logger.warning("daily_job_db_unavailable", extra={"error": str(exc)})

    if has_job_runs:
        with get_session_factory()() as session:
            summary = _execute(session, **kwargs)
            summary["db_recorded"] = True
            _record_run(session, summary)
            _logger.info("daily_job_completed", extra=summary)
            return summary

    summary = _execute(None, **kwargs)
    _logger.info("daily_job_completed", extra=summary)
    return summary


def main() -> int:
    """CLI entrypoint for `infra/scripts/daily_job.py`."""
    parser = argparse.ArgumentParser(
        description="Run PaisaProof daily market & claim job."
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
    return 0 if summary["status"] in {"ok", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
