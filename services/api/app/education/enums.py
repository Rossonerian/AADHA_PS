"""Shared enums and level-unlock mapping strictly aligned with SoT Sections 6 & 8."""
from __future__ import annotations

from enum import Enum
from typing import Dict, List


class SkillArea(str, Enum):
    BASICS = "basics"
    READING_STOCK = "reading_stock"
    JUDGING_INFO = "judging_info"
    RISK = "risk"


class ToolName(str, Enum):
    SCENARIOS = "scenarios"
    RED_FLAG_CHECK = "red_flag_check"
    EXPLAIN_STOCK = "explain_stock"
    VERIFIER = "verifier"
    DASHBOARD = "dashboard"


class AttemptItemType(str, Enum):
    QUESTION = "question"
    SCENARIO = "scenario"
    VERIFIER_GUESS = "verifier_guess"


class AttemptContext(str, Enum):
    ONBOARDING = "onboarding"
    LESSON = "lesson"
    ASSESSMENT = "assessment"
    PRACTICE = "practice"
    STUDY_PRE = "study_pre"
    STUDY_POST = "study_post"


class DataOrigin(str, Enum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class LessonStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


LEVEL_NAMES: Dict[int, str] = {
    1: "Foundations",
    2: "Reading a stock",
    3: "Judging information",
    4: "Risk & discipline",
}

# SoT Section 8: Level -> unlocks (cumulative as users advance)
LEVEL_UNLOCKS: Dict[int, List[ToolName]] = {
    1: [ToolName.SCENARIOS, ToolName.RED_FLAG_CHECK],
    2: [ToolName.EXPLAIN_STOCK],
    3: [ToolName.VERIFIER],
    4: [ToolName.DASHBOARD],
}

# Reverse lookup: minimum level required to access a given tool
TOOL_REQUIRED_LEVEL: Dict[ToolName, int] = {
    tool: level
    for level, tools in LEVEL_UNLOCKS.items()
    for tool in tools
}


def cumulative_unlocks_for_level(level: int) -> List[str]:
    """Returns ordered list of all tool names unlocked up to and including `level`."""
    clamped = max(1, min(4, int(level)))
    tools: List[str] = []
    for lvl in range(1, clamped + 1):
        for t in LEVEL_UNLOCKS[lvl]:
            tools.append(t.value)
    return tools
