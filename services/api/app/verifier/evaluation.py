"""Measure exact structured extraction precision/recall against labelled tips."""

import json
from dataclasses import dataclass
from pathlib import Path

from .extraction import AdviceRequest, extract_claim, reject_advice_request
from .ports import VerifierCore
from .schemas import ClaimStatus


@dataclass(frozen=True, slots=True)
class ExtractionMetrics:
    examples: int
    hinglish: int
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def f1(self) -> float:
        denom = 2 * self.true_positives + self.false_positives + self.false_negatives
        return 2 * self.true_positives / denom if denom else 0.0


def evaluate_file(path: Path, core: VerifierCore) -> ExtractionMetrics:
    examples = hinglish = tp = fp = fn = 0
    with path.open(encoding="utf-8") as rows:
        for row in rows:
            labelled = json.loads(row)
            examples += 1
            hinglish += labelled["lang"] == "hinglish"
            text = labelled["text"]
            expected = labelled["expected"]
            actual = None
            try:
                reject_advice_request(text)
            except AdviceRequest:
                pass
            else:
                parsed = extract_claim(text, core)
                if parsed.status == ClaimStatus.OPEN:
                    actual = {"symbol": parsed.symbol, "direction": parsed.direction, "entry": parsed.entry,
                              "target": parsed.target, "stop": parsed.stop, "window_days": parsed.window_days}
            if expected is not None and actual == expected:
                tp += 1
            elif actual != expected:
                fp += actual is not None
                fn += expected is not None
    return ExtractionMetrics(examples, hinglish, tp, fp, fn)
