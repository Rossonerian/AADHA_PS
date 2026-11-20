"""Pure mathematical scoring functions: Brier score, adaptive difficulty, placement, 95% CIs."""
from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple

try:
    from scipy import stats
except ImportError:
    stats = None

from .enums import SkillArea


def compute_brier_score(attempts: Sequence[Tuple[int, bool]]) -> float:
    """Computes Brier score for (confidence_50_to_100, is_correct) pairs.

    p = confidence / 100.0 in [0.5, 1.0], y = 1.0 if correct else 0.0.
    Brier = mean((p - y)^2) in [0.0, 1.0]. Lower is better calibrated.
    """
    if not attempts:
        return 0.25
    total = 0.0
    for conf, correct in attempts:
        if not (50 <= conf <= 100):
            raise ValueError(f"Confidence must be between 50 and 100, got {conf}")
        p = conf / 100.0
        y = 1.0 if correct else 0.0
        total += (p - y) ** 2
    return round(total / len(attempts), 4)


def next_adaptive_difficulty(current_difficulty: int, was_correct: bool) -> int:
    """Adaptive staircase: harder (+1, max 5) after correct, easier (-1, min 1) after wrong."""
    if was_correct:
        return min(5, current_difficulty + 1)
    return max(1, current_difficulty - 1)


def compute_skill_scores(
    records: Sequence[Dict[str, object]],
) -> Dict[str, float]:
    """Computes 0-100 score per skill area weighted by question difficulty.

    Each record has keys: skill_area (str), difficulty (int 1-5), correct (bool).
    """
    weighted_hits: Dict[str, float] = {s.value: 0.0 for s in SkillArea}
    weighted_total: Dict[str, float] = {s.value: 0.0 for s in SkillArea}
    for rec in records:
        area = str(rec["skill_area"])
        diff = float(rec.get("difficulty", 3))
        weight = 0.6 + 0.2 * diff  # diff 1 -> 0.8, diff 3 -> 1.2, diff 5 -> 1.6
        weighted_total[area] = weighted_total.get(area, 0.0) + weight
        if rec.get("correct"):
            weighted_hits[area] = weighted_hits.get(area, 0.0) + weight

    out: Dict[str, float] = {}
    for area in [s.value for s in SkillArea]:
        denom = weighted_total.get(area, 0.0)
        if denom <= 0:
            out[area] = 0.0
        else:
            out[area] = round(100.0 * weighted_hits[area] / denom, 2)
    return out


def determine_onboarding_level(
    accuracy_pct: float,
    brier: float,
    avg_difficulty_correct: float,
) -> int:
    """Maps onboarding accuracy (0-100), Brier score (0-1), and difficulty reached to Level 1-4.

    Calibration discipline:
    - Brier >= 0.25 is no better than blind 50/50 guessing, so users must achieve Brier < 0.25
      (or high accuracy with calibrated confidence) to advance beyond Level 1.
    - Overconfident users (high Brier > 0.30) are capped at Level 1 so they build calibration
      before unlocking higher-level tools.
    - All-wrong or random guessers land at Level 1.
    - Strong, well-calibrated users who climb to high difficulty land at Level 3 or 4.
    """
    if accuracy_pct >= 88.0 and avg_difficulty_correct >= 3.8:
        level = 4
    elif accuracy_pct >= 72.0 and avg_difficulty_correct >= 3.0:
        level = 3
    elif accuracy_pct >= 55.0:
        level = 2
    else:
        level = 1

    # Strict calibration discipline: Brier == 0.25 is random guessing baseline
    if brier >= 0.25:
        level = min(level, 1)
    elif brier > 0.22:
        level = min(level, 2)
    elif brier > 0.18 and level == 4:
        level = 3

    return max(1, min(4, level))


def paired_ci_95(deltas: Sequence[float]) -> Dict[str, float]:
    """Computes mean, std, n, and two-sided 95% Student's t confidence interval for paired deltas."""
    n = len(deltas)
    if n == 0:
        return {"n": 0, "mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "std": 0.0}
    mean_val = sum(deltas) / n
    if n == 1:
        return {
            "n": 1,
            "mean": round(mean_val, 4),
            "ci_low": round(mean_val, 4),
            "ci_high": round(mean_val, 4),
            "std": 0.0,
        }
    variance = sum((x - mean_val) ** 2 for x in deltas) / (n - 1)
    std_val = math.sqrt(variance)
    se = std_val / math.sqrt(n)
    if stats is not None:
        t_crit = float(stats.t.ppf(0.975, df=n - 1))
    else:
        # Fallback Student's t critical values for 95% two-sided CI when scipy is unavailable
        _t_table = {
            1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
            9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
            16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 25: 2.060, 30: 2.042,
            39: 2.02269, 40: 2.02107, 60: 2.0003, 120: 1.9799
        }
        df = n - 1
        t_crit = _t_table.get(df, 2.02269 if 35 <= df <= 45 else (1.96 if df > 120 else 2.0))
    margin = t_crit * se
    return {
        "n": n,
        "mean": round(mean_val, 4),
        "std": round(std_val, 4),
        "ci_low": round(mean_val - margin, 4),
        "ci_high": round(mean_val + margin, 4),
    }
