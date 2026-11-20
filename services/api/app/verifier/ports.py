"""Bindings supplied by Hardhik's shared core at integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta, timezone
from typing import Protocol, TypedDict
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
    def __call__(self, prompt: str, schema: Mapping[str, object] | None = None) -> object: ...


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


SessionFactory = Callable[[], Session]
