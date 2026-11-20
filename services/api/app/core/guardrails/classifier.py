"""Lightweight deterministic weighted-signal classifier for indirect advisory intent."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.guardrails.normalizer import NormalizedText, normalize_text
from app.core.guardrails.rules import sanitize_educational_context

INDIRECT_REASON_CODE = "indirect_advisory_intent"
CLASSIFIER_THRESHOLD = 1.0


@dataclass(frozen=True, slots=True)
class SignalRule:
    """Weighted pattern contributing to indirect advisory detection."""

    name: str
    weight: float
    pattern: re.Pattern[str]
    use_original_case: bool = False


@dataclass(frozen=True, slots=True)
class ClassifierResult:
    """Result returned by the deterministic indirect-intent classifier."""

    triggered: bool
    score: float
    threshold: float
    signals: list[str]
    reason: str | None = None


_SIGNALS: tuple[SignalRule, ...] = (
    SignalRule(
        name="roleplay_advisor",
        weight=0.85,
        pattern=re.compile(
            r"\b(?:pretend(?:ing)?\s+to\s+be|act(?:ing)?\s+as|"
            r"imagine\s+(?:you\s+are|i\s+am)|roleplay(?:ing)?\s+as|"
            r"speaking\s+as)\s+"
            r"(?:(?:a|an|your)\s+)?"
            r"(?:sebi[- ]registered\s+|sebi\s+|registered\s+)?"
            r"(?:ra|ia|advisor|adviser|analyst|broker|wealth\s+coach|"
            r"finfluencer|mentor|guru|expert)\b",
            re.IGNORECASE,
        ),
    ),
    SignalRule(
        name="hypothetical_shoe_shift",
        weight=0.65,
        pattern=re.compile(
            r"\b(?:if\s+i\s+were\s+(?:you|in\s+your\s+(?:shoes|place|position|spot))|"
            r"if\s+it\s+were\s+my\s+(?:money|capital|portfolio|savings)|"
            r"in\s+your\s+shoes|personally\s*,?\s*i['’]?d|"
            r"what\s+i\s+would\s+do\s+is|my\s+move\s+would\s+be|"
            r"just\s+between\s+us)\b",
            re.IGNORECASE,
        ),
    ),
    SignalRule(
        name="trojan_disclaimer",
        weight=0.60,
        pattern=re.compile(
            r"\b(?:for\s+educational\s+purposes?\s+only|purely\s+educational|"
            r"education\s+only|not\s+(?:a\s+)?(?:financial|investment|trading|sebi)\s+advice|"
            r"not\s+(?:a\s+)?recommendation|no\s+advice\s+intended|"
            r"purely\s+hypothetical|disclaimer\s*:|\bnfa\b|\bdyor\b)\b",
            re.IGNORECASE,
        ),
    ),
    SignalRule(
        name="smart_investor_fomo",
        weight=0.70,
        pattern=re.compile(
            r"\b(?:(?:a\s+)?smart\s+(?:investor|money|trader)s?\s+"
            r"(?:wouldn['’]?t|would\s+not|won['’]?t|never|shouldn['’]?t)\s+miss|"
            r"nobody\s+(?:wants\s+to|should)\s+miss|"
            r"you['’]?ll\s+regret\s+missing|don['’]?t\s+say\s+i\s+didn['’]?t\s+warn|"
            r"thank\s+me\s+later|mark\s+my\s+words|no[- ]brainer|"
            r"screaming\s+bargain|steal\s+at\s+this\s+(?:price|level)|"
            r"hard\s+to\s+ignore\s+at\s+this|table[- ]pounding)\b",
            re.IGNORECASE,
        ),
    ),
    SignalRule(
        name="subtle_action_nudge",
        weight=0.55,
        pattern=re.compile(
            r"\b(?:pick(?:ing)?\s+up|grab(?:bing)?|shift(?:ing)?|"
            r"mov(?:e|ing)\s+into|rotat(?:e|ing)\s+into|"
            r"park(?:ing)?\s+(?:money|cash|funds|capital|savings|it)|"
            r"deploy(?:ing)?\s+(?:money|cash|funds|capital|savings|it)|"
            r"quietly\s+(?:adding|accumulating|picking|loading)|"
            r"deserves\s+a\s+spot\s+in\s+(?:your\s+)?portfolio|"
            r"belongs\s+in\s+every\s+portfolio|"
            r"worth\s+(?:picking\s+up|grabbing|adding|deploying|accumulating|considering)|"
            r"consider\s+(?:adding|picking|entering|buying|selling|holding|accumulating|"
            r"shifting|moving|allocating)|"
            r"makes\s+(?:total\s+)?sense\s+to\s+(?:add|accumulate|pick|enter|hold|exit))\b",
            re.IGNORECASE,
        ),
    ),
    SignalRule(
        name="timing_urgency",
        weight=0.45,
        pattern=re.compile(
            r"\b(?:before\s+(?:friday|monday|tuesday|wednesday|thursday|tomorrow|"
            r"earnings|results|budget|expiry|the\s+bell|market\s+opens?|open)|"
            r"at\s+tomorrow['’]?s\s+open|this\s+(?:week|morning|afternoon)\s+only|"
            r"ready\s+to\s+(?:pop|fly|explode|break\s+out|take\s+off)|"
            r"about\s+to\s+(?:take\s+off|pop|explode|surge|fly)|"
            r"agle\s+(?:hafte|mahine|din))\b",
            re.IGNORECASE,
        ),
    ),
    SignalRule(
        name="portfolio_or_capital",
        weight=0.40,
        pattern=re.compile(
            r"\b(?:half\s+(?:my|your)\s+(?:savings|capital|portfolio|money)|"
            r"your\s+(?:savings|portfolio|capital|funds)|"
            r"(?:my|your)\s+watchlist\s+right\s+now|"
            r"(?:with|invest|put|deploy|allocate|park)\s+"
            r"(?:₹\s*\d[\d,]*|rs\.?\s*\d[\d,]*|\d+\s*(?:lakh|crore|k)))\b",
            re.IGNORECASE,
        ),
    ),
    SignalRule(
        name="valuation_or_level_cue",
        weight=0.35,
        pattern=re.compile(
            r"\b(?:at\s+this\s+valuation|at\s+these\s+levels|at\s+current\s+levels|"
            r"around\s+(?:₹|rs\.?)?\s*\d{2,6}|near\s+(?:₹|rs\.?)?\s*\d{2,6}|\bcmp\b)\b",
            re.IGNORECASE,
        ),
    ),
    SignalRule(
        name="stock_mention_hint",
        weight=0.35,
        pattern=re.compile(
            r"\b(?:"
            r"reliance|tata\s+motors|infosys|hdfc(?:\s+bank)?|icici(?:\s+bank)?|"
            r"sbi|itc|tcs|wipro|zomato|paytm|nykaa|trent|suzlon|bajaj|adani|"
            r"coal\s+india|bharti\s+airtel|l&t|dixon|kotak|axis\s+bank|ongc|"
            r"maruti|titan|asian\s+paints|sun\s+pharma|vedanta|yes\s+bank|"
            r"banknifty|nifty\s*50"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


def classify_indirect_intent(norm: NormalizedText) -> ClassifierResult:
    """Evaluate weighted indirect advisory signals over sanitized text views."""
    if not norm.cleaned:
        return ClassifierResult(
            triggered=False,
            score=0.0,
            threshold=CLASSIFIER_THRESHOLD,
            signals=[],
            reason=None,
        )

    sanitized_cleaned = sanitize_educational_context(norm.raw_cleaned)
    sanitized_norm = normalize_text(sanitized_cleaned)

    score = 0.0
    matched_signals: list[str] = []

    for sig in _SIGNALS:
        candidates = (
            [sanitized_norm.cleaned]
            if sig.use_original_case
            else [
                sanitized_norm.lower,
                sanitized_norm.deobfuscated,
                *sanitized_norm.shadow_variants,
            ]
        )
        if any(sig.pattern.search(candidate) for candidate in candidates):
            score += sig.weight
            matched_signals.append(sig.name)

    triggered = score >= CLASSIFIER_THRESHOLD
    return ClassifierResult(
        triggered=triggered,
        score=round(score, 3),
        threshold=CLASSIFIER_THRESHOLD,
        signals=matched_signals,
        reason=INDIRECT_REASON_CODE if triggered else None,
    )
