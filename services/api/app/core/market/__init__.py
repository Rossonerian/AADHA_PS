"""Shared market data interface per Source of Truth Section 5."""

from app.core.market.prices import index, prices
from app.core.market.refresh import get_market_data_as_of, refresh_all
from app.core.market.sebi import sebi_registered
from app.core.market.surveillance import surveillance
from app.core.market.symbols import resolve_symbol

__all__ = [
    "get_market_data_as_of",
    "index",
    "prices",
    "refresh_all",
    "resolve_symbol",
    "sebi_registered",
    "surveillance",
]
