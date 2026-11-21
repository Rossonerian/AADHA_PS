"""Conservative top-level data_origin aggregation helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

ResponseDataOrigin = Literal["real", "synthetic", "mixed"]


def aggregate_data_origin(
    origins: Iterable[str | None],
    *,
    empty_default: ResponseDataOrigin = "synthetic",
) -> ResponseDataOrigin:
    """Return 'real' only if all inputs are 'real', 'synthetic' if all synthetic, else 'mixed'."""
    normalized: set[str] = set()
    for raw in origins:
        val = str(raw).strip().lower() if raw is not None else ""
        if val == "real":
            normalized.add("real")
        elif val == "mixed":
            normalized.update({"real", "synthetic"})
        else:
            normalized.add("synthetic")
    if not normalized:
        return empty_default
    if normalized == {"real"}:
        return "real"
    if normalized == {"synthetic"}:
        return "synthetic"
    return "mixed"
