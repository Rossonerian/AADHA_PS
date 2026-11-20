"""Multi-layer financial-advice output guardrails for Aacharya."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.guardrails.classifier import classify_indirect_intent
from app.core.guardrails.normalizer import normalize_text
from app.core.guardrails.rules import evaluate_rules

NEUTRAL_FALLBACK: str = (
    "Aacharya is an educational platform and does not provide buy, sell, or hold "
    "recommendations, price targets, or stock picks. We focus on teaching financial "
    "reasoning and evaluating the historical accuracy of public sources."
)


class GuardResult(BaseModel):
    """Result of evaluating an output string against advisory guardrails."""

    ok: bool
    text: str
    reasons: list[str] = Field(default_factory=list)


def check_output(text: str) -> GuardResult:
    """Validate text against direct, obfuscated, Hinglish, and indirect advice rules.

    Args:
        text: Candidate output text to inspect before showing to a user.

    Returns:
        GuardResult with ``ok=True`` and unchanged ``text`` when safe, or
        ``ok=False``, ``NEUTRAL_FALLBACK``, and triggered ``reasons`` when blocked.
    """
    if not text or not text.strip():
        return GuardResult(ok=True, text=text, reasons=[])

    norm = normalize_text(text)
    reasons = evaluate_rules(norm)

    clf_result = classify_indirect_intent(norm)
    if clf_result.triggered and clf_result.reason and clf_result.reason not in reasons:
        reasons.append(clf_result.reason)

    if reasons:
        return GuardResult(ok=False, text=NEUTRAL_FALLBACK, reasons=reasons)

    return GuardResult(ok=True, text=text, reasons=[])


__all__ = ["GuardResult", "NEUTRAL_FALLBACK", "check_output"]
