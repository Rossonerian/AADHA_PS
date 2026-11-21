"""Curated SEBI identity facts and unscored, guardrail-checked search links."""

import csv
import re
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class MentionResult:
    """A guardrail-checked search hit, ready for a short database write."""

    url: str
    title: str
    published_at: datetime | None


_HANDLE_RE = re.compile(r"[\w@ .&-]{1,255}")


def apply_enforcement(source: Source, now: datetime | None = None) -> None:
    """Pure local CSV lookup; no network."""
    now = now or datetime.now(UTC)
    source.enforcement_flag, source.enforcement_refs = enforcement(
        reg_no=source.sebi_reg_no,
        legal_name=source.handle,
        origin=source.data_origin,
        as_of=now.date(),
    )


def needs_mention_refresh(
    session: Session, source: Source, core: VerifierCore, now: datetime | None = None
) -> bool:
    """Cheap read-only staleness check (no network, no row lock needed)."""
    now = now or datetime.now(UTC)
    if (
        source.handle.startswith("private-")
        or core.web_search is None
        or not _HANDLE_RE.fullmatch(source.handle)
    ):
        return False
    latest = session.scalar(
        select(SourceMention.fetched_at)
        .where(SourceMention.source_id == source.id)
        .order_by(SourceMention.fetched_at.desc())
        .limit(1)
    )
    return latest is None or now - latest.replace(tzinfo=UTC) >= timedelta(hours=24)


def fetch_mentions(
    *, handle: str, platform: str, origin: str, core: VerifierCore
) -> list[MentionResult]:
    """Network + guardrail phase. Takes plain values, never a Session or ORM row, so
    it can run outside any transaction that holds a row lock."""
    if core.web_search is None or not _HANDLE_RE.fullmatch(handle):
        return []
    # Never include tip text, search operators supplied by a user, or learner data.
    try:
        results = core.web_search(f'"{handle}" "{platform}"', limit=5)
    except AppError:
        return []
    out: list[MentionResult] = []
    for result in results:
        if result.data_origin != origin or len(str(result.url)) > 2048:
            continue
        parsed = urlsplit(str(result.url))
        if parsed.scheme != "https" or parsed.username or parsed.password:
            continue
        guard = core.check_output(result.title)
        if not guard.ok:
            continue
        out.append(MentionResult(str(result.url), guard.text, result.published_at))
    return out


def apply_mentions(
    session: Session,
    source: Source,
    mentions: list[MentionResult],
    now: datetime | None = None,
) -> None:
    """Short database write; call under the source lock, after `fetch_mentions`."""
    now = now or datetime.now(UTC)
    for item in mentions:
        row = session.scalar(
            select(SourceMention).where(
                SourceMention.source_id == source.id, SourceMention.url == item.url
            )
        )
        if row is None:
            row = SourceMention(
                source_id=source.id,
                url=item.url,
                platform=source.platform,
                data_origin=source.data_origin,
            )
            session.add(row)
        # Search descriptions are not verified verbatim page quotes; never store them.
        row.title, row.published_at, row.fetched_at = (
            item.title,
            item.published_at,
            now,
        )


def refresh(session: Session, source: Source, core: VerifierCore) -> None:
    """Compatibility wrapper: enforcement, then (if stale) fetch + write.

    Callers that hold a source row lock should instead call `needs_mention_refresh`,
    release the lock, run `fetch_mentions`, then re-lock and `apply_mentions`, so
    no HTTP happens inside a locked transaction.
    """
    if source.handle.startswith("private-"):
        return
    now = datetime.now(UTC)
    apply_enforcement(source, now)
    if not needs_mention_refresh(session, source, core, now):
        return
    mentions = fetch_mentions(
        handle=source.handle,
        platform=source.platform,
        origin=source.data_origin,
        core=core,
    )
    apply_mentions(session, source, mentions, now)
