"""Symbol normalization, Indian retail alias lookup, and fuzzy company matching."""

from __future__ import annotations

import csv
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import cast

from rapidfuzz import fuzz

from app.core.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[5]

_STOPWORDS: frozenset[str] = frozenset(
    {
        "YES",
        "IDEA",
        "TIPS",
        "CARE",
        "PAGE",
        "ALL",
        "NOW",
        "BEST",
        "JUST",
        "GOOD",
        "FREE",
        "SAFE",
        "FAST",
        "TIME",
        "LIFE",
        "STAR",
        "GOLD",
        "BANK",
        "INDIA",
        "TECH",
        "OIL",
        "GAS",
        "POWER",
        "AUTO",
        "BUY",
        "SELL",
        "HOLD",
        "HIGH",
        "LOW",
        "OPEN",
        "NEXT",
        "NEW",
        "ONE",
        "TWO",
        "UP",
        "DOWN",
        "OUT",
        "IN",
        "ON",
        "IT",
        "IS",
        "AT",
        "TO",
        "FOR",
        "WITH",
        "TARGET",
        "PROFIT",
        "LOSS",
        "NO",
        "HERE",
        "THIS",
        "THAT",
        "THE",
        "AND",
        "OR",
        "NOT",
        "REAL",
        "TRUE",
        "MORE",
        "MOST",
        "VERY",
        "WILL",
        "CAN",
        "MAY",
        "GET",
        "SET",
        "TOP",
        "BIG",
        "MAX",
        "MIN",
        "WIN",
        "PAY",
        "SURE",
        "RISK",
        "DEBT",
        "CASH",
        "FUND",
        "STOCK",
        "SHARE",
        "PRICE",
        "CALL",
        "PUT",
        "LONG",
        "SHORT",
        "BULL",
        "BEAR",
        "TODAY",
        "WEEK",
        "YEAR",
        "LATE",
        "SOON",
        "WAIT",
        "LOOK",
        "WATCH",
        "SEE",
        "TELL",
        "ASK",
        "HELP",
        "INFO",
        "NEWS",
        "ALERT",
        "NOTE",
        "POST",
        "LINK",
        "DATA",
        "TEST",
        "DEMO",
        "NSE",
        "BSE",
        "SEBI",
        "IPO",
        "SIP",
        "ETF",
        "GDP",
        "RBI",
        "ROI",
        "CAGR",
        "LTD",
        "LIMITED",
        "PVT",
        "PRIVATE",
        "CORP",
        "COMPANY",
    }
)

_CURRENCY_CODES: frozenset[str] = frozenset({"USD", "INR", "EUR", "GBP", "JPY", "AUD"})
_LEGAL_SUFFIX_WORDS: frozenset[str] = frozenset(
    {"limited", "ltd", "pvt", "private", "company", "co", "corporation", "corp"}
)
_GENERIC_FUZZY_WORDS: frozenset[str] = frozenset(
    {w.lower() for w in _STOPWORDS}
    | _LEGAL_SUFFIX_WORDS
    | {"of", "and", "the", "services", "industries", "enterprises", "financial"}
)

_CASHTAG_RE = re.compile(r"(?<![A-Za-z0-9_])\$([A-Za-z][A-Za-z0-9&-]{0,19})\b")
_EXCHANGE_SUFFIX_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9&-]{0,19})\.(?:NS|BO)\b", re.IGNORECASE
)
_EXCHANGE_PREFIX_RE = re.compile(
    r"\b(?:NSE|BSE)\s*:\s*([A-Za-z][A-Za-z0-9&-]{0,19})\b", re.IGNORECASE
)
_UPPER_TOKEN_RE = re.compile(r"\b([A-Z][A-Z0-9&-]{1,19})\b")
_STOPWORD_EQUITY_CTX_RE = re.compile(
    r"\b([A-Z]{2,15})\s+(?:stock|share|shares|equity|cmp)\b", re.IGNORECASE
)
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_CLEAN_RE = re.compile(r"[^a-z0-9&\s]")


def get_market_data_dir() -> Path:
    """Resolve the configured market data directory path across working directories."""
    raw = (os.getenv("MARKET_DATA_DIR") or get_settings().market_data_dir).strip()
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    cwd_candidate = Path.cwd() / candidate
    if cwd_candidate.exists():
        return cwd_candidate.resolve()
    return (_REPO_ROOT / candidate).resolve()


def is_test_env() -> bool:
    """Return True when runtime environment is `test` (disables implicit live network)."""
    env_val = (os.getenv("APP_ENV") or get_settings().app_env).strip().lower()
    return env_val == "test"


@lru_cache(maxsize=8)
def _load_symbol_catalog_cached(
    market_dir_str: str,
    symbols_mtime_ns: int,
    aliases_mtime_ns: int,
) -> tuple[dict[str, str], dict[str, str], list[tuple[str, str]]]:
    """Load NSE symbol table and alias table keyed by file mtimes."""
    del symbols_mtime_ns, aliases_mtime_ns
    market_dir = Path(market_dir_str)
    symbols_path = market_dir / "nse_symbols.csv"
    aliases_path = market_dir / "symbol_aliases.json"

    symbols_map: dict[str, str] = {}
    if symbols_path.exists():
        with symbols_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                sym = (row.get("symbol") or "").strip().upper()
                name = (row.get("company_name") or "").strip()
                if sym and name:
                    symbols_map[sym] = name

    aliases_map: dict[str, str] = {}
    if aliases_path.exists():
        raw_payload = json.loads(aliases_path.read_text(encoding="utf-8"))
        raw_aliases = (
            raw_payload.get("aliases", {})
            if isinstance(raw_payload, dict) and "aliases" in raw_payload
            else raw_payload
        )
        if isinstance(raw_aliases, dict):
            for alias_key, target_sym in raw_aliases.items():
                key_norm = _WHITESPACE_RE.sub(" ", str(alias_key).strip().lower())
                val_norm = str(target_sym).strip().upper()
                if key_norm and val_norm:
                    aliases_map[key_norm] = val_norm

    sorted_aliases = sorted(
        aliases_map.items(), key=lambda item: len(item[0]), reverse=True
    )
    return symbols_map, aliases_map, sorted_aliases


def load_symbol_catalog() -> (
    tuple[dict[str, str], dict[str, str], list[tuple[str, str]]]
):
    """Return `(symbols_map, aliases_map, sorted_aliases)` for the active market dir."""
    market_dir = get_market_data_dir()
    symbols_path = market_dir / "nse_symbols.csv"
    aliases_path = market_dir / "symbol_aliases.json"
    sym_mtime = symbols_path.stat().st_mtime_ns if symbols_path.exists() else 0
    alias_mtime = aliases_path.stat().st_mtime_ns if aliases_path.exists() else 0
    return _load_symbol_catalog_cached(str(market_dir), sym_mtime, alias_mtime)


def canonicalize_ticker(raw_symbol: str) -> str:
    """Normalize a raw ticker/alias string (stripping `$`, `.NS`, `.BO`) to canonical form."""
    cleaned = raw_symbol.strip().lstrip("$")
    cleaned = re.sub(r"\.(?:NS|BO)$", "", cleaned, flags=re.IGNORECASE)
    upper = cleaned.upper()
    symbols_map, aliases_map, _ = load_symbol_catalog()
    if upper in symbols_map:
        return upper
    alias_target = aliases_map.get(cleaned.lower())
    if alias_target:
        return alias_target
    return upper


def _strip_legal_suffix(name: str) -> str:
    tokens = _PUNCT_CLEAN_RE.sub(" ", name.lower()).split()
    kept = [tok for tok in tokens if tok not in _LEGAL_SUFFIX_WORDS]
    return " ".join(kept) if kept else " ".join(tokens)


def _match_explicit_symbol(
    text: str,
    symbols_map: dict[str, str],
    aliases_map: dict[str, str],
) -> str | None:
    for pattern, allow_unknown in (
        (_EXCHANGE_SUFFIX_RE, True),
        (_EXCHANGE_PREFIX_RE, True),
        (_CASHTAG_RE, False),
    ):
        for match in pattern.finditer(text):
            raw = match.group(1).strip()
            upper = raw.upper()
            if upper in _CURRENCY_CODES:
                continue
            if upper in symbols_map:
                return upper
            alias_hit = aliases_map.get(raw.lower())
            if alias_hit:
                return alias_hit
            if allow_unknown and len(upper) >= 2 and upper not in _STOPWORDS:
                return upper
            if (
                not allow_unknown
                and raw.isupper()
                and len(upper) >= 2
                and upper not in _STOPWORDS
            ):
                return upper
    return None


def _match_uppercase_token(
    text: str,
    symbols_map: dict[str, str],
    aliases_map: dict[str, str],
) -> str | None:
    tokens: list[str] = _UPPER_TOKEN_RE.findall(text)
    for token in tokens:
        if token in _STOPWORDS:
            continue
        if token in symbols_map:
            return token
    for token in tokens:
        if token in _STOPWORDS:
            continue
        alias_hit = aliases_map.get(token.lower())
        if alias_hit:
            return alias_hit
    for ctx_match in _STOPWORD_EQUITY_CTX_RE.finditer(text):
        token = ctx_match.group(1)
        if token.isupper() and token in symbols_map:
            return token
    return None


def _match_alias_phrase(text: str, sorted_aliases: list[tuple[str, str]]) -> str | None:
    normalized = _WHITESPACE_RE.sub(" ", text.strip().lower())
    if not normalized:
        return None
    for alias, symbol in sorted_aliases:
        pattern = rf"(?:^|[^a-z0-9]){re.escape(alias)}(?=$|[^a-z0-9])"
        if re.search(pattern, normalized):
            return symbol
    return None


def _fuzzy_match_company(text: str, symbols_map: dict[str, str]) -> str | None:
    if not symbols_map:
        return None
    cleaned_input = _WHITESPACE_RE.sub(
        " ", _PUNCT_CLEAN_RE.sub(" ", text.lower())
    ).strip()
    if not cleaned_input:
        return None

    words = cleaned_input.split()
    if len(words) <= 6:
        phrases = [_strip_legal_suffix(cleaned_input), cleaned_input]
    else:
        phrases = []
        max_win = min(5, len(words))
        for win_len in range(2, max_win + 1):
            for idx in range(0, len(words) - win_len + 1):
                segment = words[idx : idx + win_len]
                distinctive = [w for w in segment if w not in _GENERIC_FUZZY_WORDS]
                if len(distinctive) >= 1 and (
                    len(distinctive) >= 2 or len(distinctive[0]) >= 6
                ):
                    phrases.append(" ".join(segment))

    if not phrases:
        return None

    targets: list[tuple[str, str, str]] = [
        (sym, name.lower(), _strip_legal_suffix(name))
        for sym, name in symbols_map.items()
    ]

    best_symbol: str | None = None
    best_score = 0.0

    for phrase in phrases:
        phrase_words = phrase.split()
        distinctive_phrase = [w for w in phrase_words if w not in _GENERIC_FUZZY_WORDS]
        if not distinctive_phrase:
            continue
        if len(distinctive_phrase) == 1 and len(distinctive_phrase[0]) < 6:
            continue

        for sym, full_lower, stripped_lower in targets:
            for target_name in (stripped_lower, full_lower):
                if not target_name:
                    continue
                set_score = float(fuzz.token_set_ratio(phrase, target_name))
                sort_score = float(fuzz.token_sort_ratio(phrase, target_name))
                w_score = float(fuzz.WRatio(phrase, target_name))
                if set_score >= 86.0 and max(sort_score, w_score) >= 82.0:
                    combined = (set_score + max(sort_score, w_score)) / 2.0
                    if combined > best_score:
                        best_score = combined
                        best_symbol = sym

    return cast(str | None, best_symbol)


def resolve_symbol(text: str) -> str | None:
    """Resolve a cashtag, ticker, retail alias, or company name to an NSE symbol."""
    if not text or not text.strip():
        return None

    symbols_map, aliases_map, sorted_aliases = load_symbol_catalog()

    explicit = _match_explicit_symbol(text, symbols_map, aliases_map)
    if explicit is not None:
        return explicit

    exact_upper = _match_uppercase_token(text, symbols_map, aliases_map)
    if exact_upper is not None:
        return exact_upper

    alias_match = _match_alias_phrase(text, sorted_aliases)
    if alias_match is not None:
        return alias_match

    return _fuzzy_match_company(text, symbols_map)
