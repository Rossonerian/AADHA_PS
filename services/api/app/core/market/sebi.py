"""SEBI Research Analyst (RA) and Investment Adviser (IA) registry lookup."""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.market.symbols import get_market_data_dir

_REG_NO_RE = re.compile(r"\b(IN[HA]\d{9})\b", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")
_LEGAL_SUFFIX_TOKENS: frozenset[str] = frozenset({"ltd", "limited", "pvt", "private"})
_GENERIC_ENTITY_TOKENS: frozenset[str] = frozenset(
    {
        "ltd",
        "limited",
        "pvt",
        "private",
        "securities",
        "financial",
        "services",
        "advisory",
        "advisers",
        "advisor",
        "capital",
        "wealth",
        "india",
        "research",
        "management",
        "investments",
        "investment",
        "group",
        "and",
        "of",
    }
)


def _normalize_entity_name(name: str, *, strip_legal: bool = True) -> str:
    cleaned = _WHITESPACE_RE.sub(" ", _PUNCT_RE.sub(" ", name.lower())).strip()
    if not strip_legal:
        return cleaned
    tokens = [tok for tok in cleaned.split() if tok not in _LEGAL_SUFFIX_TOKENS]
    return " ".join(tokens) if tokens else cleaned


@lru_cache(maxsize=8)
def _load_sebi_records_cached(
    csv_path_str: str,
    mtime_ns: int,
) -> list[dict[str, str]]:
    del mtime_ns
    csv_path = Path(csv_path_str)
    if not csv_path.exists():
        return []
    records: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            status = (row.get("status") or "").strip().lower()
            reg_no = (row.get("reg_no") or "").strip().upper()
            reg_type = (row.get("type") or "").strip().upper()
            name = (row.get("name") or "").strip()
            if status == "active" and reg_no and reg_type in {"RA", "IA"} and name:
                records.append(
                    {
                        "reg_no": reg_no,
                        "type": reg_type,
                        "name": name,
                        "norm_name": _normalize_entity_name(name, strip_legal=True),
                        "full_norm_name": _normalize_entity_name(
                            name, strip_legal=False
                        ),
                    }
                )
    return records


def _load_sebi_records() -> list[dict[str, str]]:
    csv_path = get_market_data_dir() / "sebi_ra_ia.csv"
    mtime = csv_path.stat().st_mtime_ns if csv_path.exists() else 0
    return _load_sebi_records_cached(str(csv_path), mtime)


def sebi_registered(name_or_reg_no: str) -> dict[str, Any]:
    """Check whether `name_or_reg_no` matches an active SEBI RA/IA registration."""
    not_found: dict[str, Any] = {"found": False, "type": None, "reg_no": None}
    if not name_or_reg_no or not name_or_reg_no.strip():
        return not_found

    records = _load_sebi_records()
    if not records:
        return not_found

    query_stripped = name_or_reg_no.strip()
    reg_match = _REG_NO_RE.search(
        query_stripped.upper().replace("-", "").replace(" ", "")
    )
    if reg_match:
        target_reg = reg_match.group(1).upper()
        for rec in records:
            if rec["reg_no"] == target_reg:
                return {
                    "found": True,
                    "type": rec["type"],
                    "reg_no": rec["reg_no"],
                }
        return not_found

    compact_upper = re.sub(r"[\s-]+", "", query_stripped.upper())
    if compact_upper.startswith(("INH", "INA")):
        for rec in records:
            if rec["reg_no"] == compact_upper:
                return {
                    "found": True,
                    "type": rec["type"],
                    "reg_no": rec["reg_no"],
                }
        return not_found

    norm_query = _normalize_entity_name(query_stripped, strip_legal=True)
    full_query = _normalize_entity_name(query_stripped, strip_legal=False)
    if not norm_query:
        return not_found

    for rec in records:
        if full_query == rec["full_norm_name"] or norm_query == rec["norm_name"]:
            return {"found": True, "type": rec["type"], "reg_no": rec["reg_no"]}

    query_tokens = norm_query.split()
    distinctive = [tok for tok in query_tokens if tok not in _GENERIC_ENTITY_TOKENS]
    if not distinctive or (len(query_tokens) < 2 and len(distinctive[0]) < 8):
        return not_found

    phrase_matches: list[dict[str, str]] = []
    phrase_pattern = rf"(?:^|\s){re.escape(norm_query)}(?=$|\s)"
    for rec in records:
        if re.search(phrase_pattern, rec["norm_name"]):
            phrase_matches.append(rec)

    if len(phrase_matches) == 1:
        matched = phrase_matches[0]
        return {
            "found": True,
            "type": matched["type"],
            "reg_no": matched["reg_no"],
        }

    return not_found
