"""Curated SEBI identity facts and unscored, guardrail-checked search links."""

import csv
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError

from .models import Source, SourceMention
from .ports import VerifierCore

ORDERS = Path(__file__).resolve().parents[4] / "data/seed/market/sebi_orders.csv"


def enforcement(
    *,
    reg_no: str | None,
    legal_name: str,
    origin: str,
    as_of: date,
    path: Path = ORDERS,
) -> tuple[bool | None, list[dict[str, Any]]]:
    """No fuzzy names, aliases, allegations from search, or synthetic/real mixing."""
    if not path.exists():
        return None, []
    refs = []
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["data_origin"] != origin:
                continue
            if not (
                (
                    reg_no
                    and row["reg_no"].strip().casefold() == reg_no.strip().casefold()
                )
                or row["name"].strip().casefold() == legal_name.strip().casefold()
            ):
                continue
            try:
                if (
                    not date.fromisoformat(row["order_date"])
                    <= date.fromisoformat(row["as_of_date"])
                    <= as_of
                ):
                    continue
                url = urlsplit(row["order_url"])
                if url.scheme != "https" or url.netloc != "www.sebi.gov.in":
                    continue
                refs.append(
                    {
                        k: row[k]
                        for k in (
                            "reg_no",
                            "name",
                            "order_date",
                            "order_url",
                            "summary",
                            "as_of_date",
                            "data_origin",
                        )
                    }
                )
            except (ValueError, KeyError):
                continue
    # This is a small curated list, not a complete all-clear registry.
    return (True if refs else None), refs


def refresh(session: Session, source: Source, core: VerifierCore) -> None:
    if source.handle.startswith("private-"):
        return
    now = datetime.now(UTC)
    source.enforcement_flag, source.enforcement_refs = enforcement(
        reg_no=source.sebi_reg_no,
        legal_name=source.handle,
        origin=source.data_origin,
        as_of=now.date(),
    )
    if core.web_search is None:
        return
    latest = session.scalar(
        select(SourceMention.fetched_at)
        .where(SourceMention.source_id == source.id)
        .order_by(SourceMention.fetched_at.desc())
        .limit(1)
    )
    if latest is not None and now - latest.replace(tzinfo=UTC) < timedelta(hours=24):
        return
    # Never include tip text, search operators supplied by a user, or learner data.
    import re

    if not re.fullmatch(r"[\w@ .&-]{1,255}", source.handle):
        return
    query = f'"{source.handle}" "{source.platform}"'
    try:
        results = core.web_search(query, limit=5)
    except AppError:
        return
    for result in results:
        if result.data_origin != source.data_origin or len(str(result.url)) > 2048:
            continue
        parsed = urlsplit(str(result.url))
        if parsed.scheme != "https" or parsed.username or parsed.password:
            continue
        guard = core.check_output(result.title)
        if not guard.ok:
            continue
        row = session.scalar(
            select(SourceMention).where(
                SourceMention.source_id == source.id,
                SourceMention.url == str(result.url),
            )
        )
        if row is None:
            row = SourceMention(
                source_id=source.id,
                url=str(result.url),
                platform=source.platform,
                data_origin=source.data_origin,
            )
            session.add(row)
        row.title, row.published_at, row.fetched_at = (
            guard.text,
            result.published_at,
            now,
        )
        # Search descriptions are not verified verbatim page quotes; never store/display them.
