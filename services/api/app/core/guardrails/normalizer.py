"""Text normalization and obfuscation-decoding utilities for output guardrails."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Invisible / zero-width characters commonly used to evade keyword filters.
_ZERO_WIDTH_RE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff\u00ad\u034f]"
)

# Normalize typographic quotes and dashes while preserving standard ASCII punctuation.
_PUNCT_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)

# Cyrillic and Greek lookalike homoglyphs mapped to lowercase ASCII equivalents.
_HOMOGLYPH_MAP = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "ё": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ї": "i",
        "ј": "j",
        "к": "k",
        "м": "m",
        "н": "h",
        "т": "t",
        "в": "b",
        "ѕ": "s",
        "α": "a",
        "β": "b",
        "ε": "e",
        "ι": "i",
        "κ": "k",
        "μ": "u",
        "ν": "v",
        "ο": "o",
        "ρ": "p",
        "ς": "s",
        "τ": "t",
        "χ": "x",
    }
)

# Punctuation-separated single characters (e.g., "b.u.y", "s*e*l*l", "p.a.k.k.a", "b-u-y").
# Does NOT cross spaces so "p.a.k.k.a p.r.o.f.i.t" becomes "pakka profit".
_PUNCT_SPACED_CHARS_RE = re.compile(
    r"(?<![a-z0-9@$!])"
    r"([a-z0-9@$!])"
    r"(?:[.*_\-/~|`']+(?=[a-z0-9@$!]))"
    r"(?:([a-z0-9@$!])[.*_\-/~|`']+)*"
    r"([a-z0-9@$!])"
    r"(?![a-z0-9@$!])"
)

# Space-separated single characters (3+ chars), stopping at double-spaces or multi-char words:
# e.g., "l o a d  u p  o n" -> "load  up  on", "s e l l Paytm" -> "sell Paytm".
_SPACE_SPACED_CHARS_RE = re.compile(
    r"(?<![a-z0-9@$!])" r"([a-z0-9@$!])" r"(?: ([a-z0-9@$!])){2,}" r"(?![a-z0-9@$!])"
)

# Two-character space-separated obfuscations of common short triggers like "u p" or "o n"
# when adjacent to another spaced run.
_TWO_CHAR_SPACED_RE = re.compile(
    r"(?<![a-z0-9@$!])"
    r"(?:u p|o n|i n|t o|a t|d o|l o|l e|k o|t p|s l)"
    r"(?=(?: {2,}|$))"
)

# Shorter fragment obfuscations joined by non-space obfuscation symbols,
# e.g., "bu.y", "b*uy", "tar_get", "ho|d".
_SPLIT_WORD_PUNCT_RE = re.compile(r"(?<=[a-z0-9@$!])[.*_|~`^]+(?=[a-z0-9@$!])")

# Hyphenated obfuscations of tiny fragments (<=2 chars on both sides),
# e.g., "b-uy", "bu-y", "be-ch", without merging "buy-and-hold" or "stop-loss".
_TINY_HYPHEN_RE = re.compile(r"\b([a-z0-9@$!]{1,2})-([a-z0-9@$!]{1,2})\b")

_LEET_TOKEN_RE = re.compile(r"\S+")
_HAS_ALPHA_RE = re.compile(r"[a-z]")
_HAS_LEET_CHAR_RE = re.compile(r"[@$!013457]")

_LEET_BASE_MAP = str.maketrans(
    {
        "@": "a",
        "4": "a",
        "3": "e",
        "0": "o",
        "5": "s",
        "7": "t",
    }
)


@dataclass(frozen=True, slots=True)
class NormalizedText:
    """Normalized representations of a text string for multi-layer rule matching."""

    original: str
    raw_lower: str
    raw_cleaned: str
    cleaned: str
    lower: str
    deobfuscated: str
    shadow_variants: tuple[str, ...]


def _collapse_spaced_chars(text: str) -> str:
    """Collapse obfuscated character-by-character runs while preserving word gaps."""
    collapsed = _PUNCT_SPACED_CHARS_RE.sub(
        lambda m: re.sub(r"[.*_\-/~|`']+", "", m.group(0)),
        text,
    )
    collapsed = _SPACE_SPACED_CHARS_RE.sub(
        lambda m: m.group(0).replace(" ", ""),
        collapsed,
    )
    collapsed = _TWO_CHAR_SPACED_RE.sub(
        lambda m: m.group(0).replace(" ", ""), collapsed
    )
    return collapsed


def _decode_leet_tokens(text: str, *, one_as_l: bool = False) -> str:
    """Decode leetspeak inside mixed tokens without corrupting trailing punctuation."""
    one_char = "l" if one_as_l else "i"

    def _transform(match: re.Match[str]) -> str:
        token = match.group(0)
        if not (_HAS_ALPHA_RE.search(token) and _HAS_LEET_CHAR_RE.search(token)):
            return token
        # Preserve trailing sentence punctuation like "week!" while decoding internal "kh@r!d0".
        out = token.translate(_LEET_BASE_MAP).replace("1", one_char)
        out = re.sub(r"!(?=[a-z0-9])", "i", out)
        out = re.sub(r"\$(?=[a-z0-9])|(?<=[a-z0-9])\$", "s", out)
        return out

    return _LEET_TOKEN_RE.sub(_transform, text)


def normalize_text(text: str) -> NormalizedText:
    """Normalize Unicode, strip zero-width chars, and build deobfuscated shadows."""
    raw_lower = unicodedata.normalize("NFKC", text).lower()

    no_zw = _ZERO_WIDTH_RE.sub("", unicodedata.normalize("NFKC", text))
    no_zw = no_zw.translate(_PUNCT_TRANSLATION)

    # Collapse obfuscated character runs BEFORE normalizing multi-spaces so
    # double spaces ("l o a d  u p  o n") act as word separators.
    homoglyph_lower = no_zw.lower().translate(_HOMOGLYPH_MAP)
    deobf = _collapse_spaced_chars(homoglyph_lower)
    deobf = _SPLIT_WORD_PUNCT_RE.sub("", deobf)
    deobf = _TINY_HYPHEN_RE.sub(r"\1\2", deobf)
    deobf = _TINY_HYPHEN_RE.sub(r"\1\2", deobf)
    deobf = re.sub(r"[ \t\r\f\v]+", " ", deobf).strip()

    cleaned = re.sub(r"[ \t\r\f\v]+", " ", no_zw).strip()
    lower = cleaned.lower()

    shadow_i = _decode_leet_tokens(deobf, one_as_l=False)
    shadow_l = _decode_leet_tokens(deobf, one_as_l=True)
    variants = (shadow_i,) if shadow_i == shadow_l else (shadow_i, shadow_l)

    return NormalizedText(
        original=text,
        raw_lower=raw_lower,
        raw_cleaned=no_zw.strip(),
        cleaned=cleaned,
        lower=lower,
        deobfuscated=deobf,
        shadow_variants=variants,
    )
