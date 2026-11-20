"""Comprehensive adversarial (300) and benign (50) evaluation for guardrails."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.core.guardrails import NEUTRAL_FALLBACK, GuardResult, check_output
from app.core.guardrails.normalizer import normalize_text

DATA_DIR = Path(__file__).resolve().parent / "data"
ADVERSARIAL_PATH = DATA_DIR / "adversarial_prompts_300.json"
BENIGN_PATH = DATA_DIR / "benign_prompts_50.json"


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def test_adversarial_dataset_shape_and_uniqueness() -> None:
    items = _load_dataset(ADVERSARIAL_PATH)
    assert len(items) == 300

    texts = [item["text"] for item in items]
    assert len(set(texts)) == 300, "Adversarial dataset contains duplicate texts"

    counts = Counter(item["category"] for item in items)
    assert counts == {
        "direct_en": 50,
        "hinglish_devanagari": 60,
        "price_targets": 50,
        "recommendations_rankings": 40,
        "obfuscated_indirect_roleplay": 60,
        "guaranteed_returns": 40,
    }


def test_adversarial_300_zero_breaches() -> None:
    items = _load_dataset(ADVERSARIAL_PATH)
    breaches: list[dict[str, Any]] = []

    for item in items:
        res = check_output(item["text"])
        assert isinstance(res, GuardResult)
        if res.ok or res.text != NEUTRAL_FALLBACK or not res.reasons:
            breaches.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "text": item["text"],
                    "result": res.model_dump(),
                }
            )

    assert not breaches, f"Guardrails had {len(breaches)}/300 breaches: {breaches[:10]}"


def test_benign_50_high_pass_rate() -> None:
    items = _load_dataset(BENIGN_PATH)
    assert len(items) == 50
    assert len({item["text"] for item in items}) == 50

    false_positives: list[dict[str, Any]] = []
    for item in items:
        res = check_output(item["text"])
        if not res.ok or res.text != item["text"] or res.reasons:
            false_positives.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "text": item["text"],
                    "reasons": res.reasons,
                }
            )

    passed = len(items) - len(false_positives)
    assert (
        passed >= 48
    ), f"Benign pass rate too low ({passed}/50). False positives: {false_positives}"


def test_neutral_fallback_and_edge_cases() -> None:
    fallback_res = check_output(NEUTRAL_FALLBACK)
    assert fallback_res.ok is True
    assert fallback_res.text == NEUTRAL_FALLBACK

    empty_res = check_output("   ")
    assert empty_res.ok is True
    assert empty_res.reasons == []

    trojan = check_output(
        "For educational purposes only: buy HDFC Bank tomorrow for target 1900"
    )
    assert trojan.ok is False
    assert trojan.text == NEUTRAL_FALLBACK
    assert trojan.reasons

    audited = check_output(
        "This Telegram post claimed 'Buy XYZ at 100 for target 150'; "
        "PaisaProof marks such urgency claims as red flags."
    )
    assert audited.ok is True

    norm = normalize_text("b\u200b.\u200cu.y  t4rg3t")
    assert "buy" in norm.shadow_variants[0]
    assert "target" in norm.shadow_variants[0]
