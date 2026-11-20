"""Shared enums and level-unlock mapping strictly aligned with SoT Sections 6 & 8."""

from __future__ import annotations

from enum import StrEnum


class SkillArea(StrEnum):
    BASICS = "basics"
    READING_STOCK = "reading_stock"
    JUDGING_INFO = "judging_info"
    RISK = "risk"


class ToolName(StrEnum):
    SCENARIOS = "scenarios"
    RED_FLAG_CHECK = "red_flag_check"
    EXPLAIN_STOCK = "explain_stock"
    VERIFIER = "verifier"
    DASHBOARD = "dashboard"


class AttemptItemType(StrEnum):
    QUESTION = "question"
    SCENARIO = "scenario"
    VERIFIER_GUESS = "verifier_guess"


class AttemptContext(StrEnum):
    ONBOARDING = "onboarding"
    LESSON = "lesson"
    ASSESSMENT = "assessment"
    PRACTICE = "practice"
    STUDY_PRE = "study_pre"
    STUDY_POST = "study_post"


class DataOrigin(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class LessonStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


LEVEL_NAMES: dict[int, str] = {
    1: "Foundations",
    2: "Reading a stock",
    3: "Judging information",
    4: "Risk & discipline",
}

# SoT Section 8: Level -> unlocks (cumulative as users advance)
LEVEL_UNLOCKS: dict[int, list[ToolName]] = {
    1: [ToolName.SCENARIOS, ToolName.RED_FLAG_CHECK],
    2: [ToolName.EXPLAIN_STOCK],
    3: [ToolName.VERIFIER],
    4: [ToolName.DASHBOARD],
}

# Reverse lookup: minimum level required to access a given tool
TOOL_REQUIRED_LEVEL: dict[ToolName, int] = {
    tool: level for level, tools in LEVEL_UNLOCKS.items() for tool in tools
}


def cumulative_unlocks_for_level(level: int) -> list[str]:
    """Returns ordered list of all tool names unlocked up to and including `level`."""
    clamped = max(1, min(4, int(level)))
    tools: list[str] = []
    for lvl in range(1, clamped + 1):
        for t in LEVEL_UNLOCKS[lvl]:
            tools.append(t.value)
    return tools
