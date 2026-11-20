"""Bindings supplied by Hardhik's shared core at integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta, timezone
from typing import Any, Protocol, TypedDict
from uuid import UUID

from pandas import DataFrame
from sqlalchemy.orm import Session

MARKET_TZ = timezone(timedelta(hours=5, minutes=30), "IST")


class User(Protocol):
    @property
    def id(self) -> UUID | str: ...

    @property
    def level(self) -> int: ...


class GuardResult(Protocol):
    @property
    def text(self) -> str: ...

    @property
    def ok(self) -> bool: ...


class Registration(TypedDict):
    found: bool
    type: str | None
    reg_no: str | None


class Market(Protocol):
    def prices(self, symbol: str, start: date, end: date) -> DataFrame: ...
    def index(self, name: str, start: date, end: date) -> DataFrame: ...
    def resolve_symbol(self, text: str) -> str | None: ...
    def surveillance(self, symbol: str, date: date) -> str | int | None: ...
    def sebi_registered(self, name_or_reg_no: str) -> Registration: ...


class Complete(Protocol):
    def __call__(self, prompt: str, schema: dict[str, Any] | None = None) -> object: ...


@dataclass(frozen=True, slots=True)
class VerifierCore:
    complete: Complete
    check_output: Callable[[str], GuardResult]
    market: Market
    # These facts are not exposed by the current SoT market interface. Unknown is not false.
    market_cap_bucket: Callable[[str, date], str | None] | None = None
    post_deleted: Callable[[str], bool | None] | None = None
    # True only if historical nominal levels and the returned OHLC bars share a price basis.
    nominal_price_basis: Callable[[str, date, date], bool] | None = None
    market_cap_provenance: Callable[[str, date], dict[str, str]] | None = None
    deletion_provenance: Callable[[str], dict[str, str]] | None = None


SessionFactory = Callable[[], Session]


class _PlatformMarket:
    """Adapter bridging `app.core.market` into the typed `Market` protocol."""

    def prices(self, symbol: str, start: date, end: date) -> DataFrame:
        from app.core import market

        return market.prices(symbol, start, end)

    def index(self, name: str, start: date, end: date) -> DataFrame:
        from app.core import market

        return market.index(name, start, end)

    def resolve_symbol(self, text: str) -> str | None:
        from app.core import market

        return market.resolve_symbol(text)

    def surveillance(self, symbol: str, date: date) -> str | int | None:
        from app.core import market

        return market.surveillance(symbol, date)

    def sebi_registered(self, name_or_reg_no: str) -> Registration:
        from app.core import market

        raw = market.sebi_registered(name_or_reg_no)
        reg_type = raw.get("type")
        reg_no = raw.get("reg_no")
        return {
            "found": bool(raw.get("found")),
            "type": str(reg_type) if reg_type is not None else None,
            "reg_no": str(reg_no) if reg_no is not None else None,
        }


def platform_core() -> VerifierCore:
    """Bind Verifier dependencies to Hardhik's shared `app.core` modules."""
    from app.core import guardrails, llm
    from app.verifier.evidence import EvidenceProviders

    evidence = EvidenceProviders()

    def _complete(prompt: str, schema: dict[str, Any] | None = None) -> object:
        if schema is None:
            return llm.complete(prompt)
        return llm.complete(prompt, schema)

    return VerifierCore(
        complete=_complete,
        check_output=guardrails.check_output,
        market=_PlatformMarket(),
        market_cap_bucket=evidence.market_cap_bucket,
        market_cap_provenance=evidence.market_cap_provenance,
        post_deleted=evidence.post_deleted,
        deletion_provenance=evidence.deletion_provenance,
    )
