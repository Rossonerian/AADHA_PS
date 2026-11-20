"""Configurable thresholds and runtime settings for the Education module."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EducationConfig:
    # Onboarding adaptive quiz parameters (SoT / Phase 2: 12-15 questions)
    onboarding_min_questions: int = 12
    onboarding_max_questions: int = 15
    onboarding_start_difficulty: int = 3  # Medium on 1-5 scale

    # Assessment parameters (Phase 4: 10 questions + 2 scenarios, >= 70% & Brier <= 0.25)
    assessment_question_count: int = 10
    assessment_scenario_count: int = 2
    assessment_pass_accuracy: float = float(os.environ.get("EDU_PASS_ACCURACY", "0.70"))
    assessment_max_brier: float = float(os.environ.get("EDU_MAX_BRIER", "0.25"))

    # Study mode parameters (Phase 6: unseen items for study_pre / study_post)
    study_question_count: int = 8
    study_scenario_count: int = 2

    # Scenario direction threshold (% move considered flat if within +-1.5%)
    scenario_flat_band_pct: float = 1.5

    # Level bounds (SoT Section 8)
    min_level: int = 1
    max_level: int = 4


DEFAULT_CONFIG = EducationConfig()
