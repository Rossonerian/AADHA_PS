"""Shared enumerations and level unlock mappings per Source of Truth Section 8."""

from enum import StrEnum


class DataOrigin(StrEnum):
    """Origin badge required on all surfaced records."""

    REAL = "real"
    SYNTHETIC = "synthetic"


class SourceLabel(StrEnum):
    """Reliability classifications for information sources."""

    RELIABLE = "reliable"
    SEMI_RELIABLE = "semi_reliable"
    NOT_RELIABLE = "not_reliable"
    NOT_ENOUGH_HISTORY = "not_enough_history"


class RedFlagCode(StrEnum):
    """Canonical red-flag identifiers for claims and messages."""

    GUARANTEED_RETURNS = "guaranteed_returns"
    URGENCY = "urgency"
    ILLIQUID_SMALL_CAP = "illiquid_small_cap"
    SURVEILLANCE_LIST = "surveillance_list"
    PRE_POST_VOLUME_SPIKE = "pre_post_volume_spike"
    NOT_SEBI_REGISTERED = "not_sebi_registered"
    VAGUE_CLAIM = "vague_claim"
    DELETED_POST = "deleted_post"


class ToolName(StrEnum):
    """Platform tool identifiers unlocked progressively by user level."""

    SCENARIOS = "scenarios"
    RED_FLAG_CHECK = "red_flag_check"
    EXPLAIN_STOCK = "explain_stock"
    VERIFIER = "verifier"
    DASHBOARD = "dashboard"


LEVEL_UNLOCKS: dict[int, list[ToolName]] = {
    1: [ToolName.SCENARIOS, ToolName.RED_FLAG_CHECK],
    2: [ToolName.SCENARIOS, ToolName.RED_FLAG_CHECK, ToolName.EXPLAIN_STOCK],
    3: [
        ToolName.SCENARIOS,
        ToolName.RED_FLAG_CHECK,
        ToolName.EXPLAIN_STOCK,
        ToolName.VERIFIER,
    ],
    4: [
        ToolName.SCENARIOS,
        ToolName.RED_FLAG_CHECK,
        ToolName.EXPLAIN_STOCK,
        ToolName.VERIFIER,
        ToolName.DASHBOARD,
    ],
}
