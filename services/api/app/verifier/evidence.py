"""Reviewed real evidence only. Missing, invalid, stale or future facts stay unknown.

These registries are deployment-controlled files, never submitted by API users.
There is no network inference of deletion from a timeout, login wall or 404.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

DEFAULT_DIR = Path(__file__).resolve().parents[4] / "data/evidence/verifier"


class MarketCapFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str
    bucket: Literal["large_cap", "mid_cap", "small_cap"]
    average_market_cap_inr_crore: float = Field(gt=0, allow_inf_nan=False)
    period_end: date
    observed_on: date
    valid_until: date
    source_url: HttpUrl
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page: int = Field(ge=1)
    data_origin: Literal["real"]


class DeletionFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    post_url: HttpUrl
    evidence_url: HttpUrl
    previous_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    previously_observed_at: datetime
    confirmed_at: datetime
    confirmation: Literal["publisher_confirmation", "platform_deleted_notice"]
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    data_origin: Literal["real"]


class EvidenceProviders:
    def __init__(self, directory: Path = DEFAULT_DIR):
        self.directory = directory

    def _rows(self, name: str) -> list[object]:
        try:
            value = json.loads((self.directory / name).read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, ValueError):
            return []

    def market_cap_fact(self, symbol: str, applicable: date) -> MarketCapFact | None:
        facts = []
        for row in self._rows("market_cap.json"):
            try:
                fact = MarketCapFact.model_validate(row)
            except ValidationError:
                continue
            if (
                fact.symbol == symbol
                and fact.period_end < fact.observed_on <= applicable <= fact.valid_until
                and fact.source_url.host
                in {"www.amfiindia.com", "portal.amfiindia.com"}
            ):
                facts.append(fact)
        if not facts:
            return None
        latest = max(f.period_end for f in facts)
        matches = [f for f in facts if f.period_end == latest]
        return matches[0] if len({f.bucket for f in matches}) == 1 else None

    def market_cap_bucket(self, symbol: str, applicable: date) -> str | None:
        fact = self.market_cap_fact(symbol, applicable)
        return fact.bucket if fact else None

    def market_cap_provenance(self, symbol: str, applicable: date) -> dict[str, str]:
        fact = self.market_cap_fact(symbol, applicable)
        return (
            {
                "source_url": str(fact.source_url),
                "observed_on": str(fact.observed_on),
                "period_end": str(fact.period_end),
            }
            if fact
            else {}
        )

    def deletion_fact(self, post_url: str) -> DeletionFact | None:
        for row in self._rows("confirmed_deletions.json"):
            try:
                fact = DeletionFact.model_validate(row)
            except ValidationError:
                continue
            before, after = fact.previously_observed_at, fact.confirmed_at
            if before.tzinfo is None or after.tzinfo is None:
                continue
            if str(fact.post_url) == post_url and before < after <= datetime.now(UTC):
                return fact
        return None

    def post_deleted(self, post_url: str) -> bool | None:
        return True if self.deletion_fact(post_url) else None

    def deletion_provenance(self, post_url: str) -> dict[str, str]:
        fact = self.deletion_fact(post_url)
        return (
            {
                "source_url": str(fact.evidence_url),
                "confirmed_at": fact.confirmed_at.isoformat(),
                "confirmation": fact.confirmation,
                "evidence_sha256": fact.evidence_sha256,
            }
            if fact
            else {}
        )
