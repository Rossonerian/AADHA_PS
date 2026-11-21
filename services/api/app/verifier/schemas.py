"""Verifier requests and responses. Claim prices describe the submitted tip only."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.provenance import ResponseDataOrigin


class DataOrigin(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class SourceLabel(StrEnum):
    RELIABLE = "reliable"
    SEMI_RELIABLE = "semi_reliable"
    NOT_RELIABLE = "not_reliable"
    NOT_ENOUGH_HISTORY = "not_enough_history"


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"


class ClaimStatus(StrEnum):
    OPEN = "open"
    SCORED = "scored"
    NEEDS_REVIEW = "needs_review"
    UNSCORABLE = "unscorable"


class RedFlagCode(StrEnum):
    GUARANTEED_RETURNS = "guaranteed_returns"
    URGENCY = "urgency"
    ILLIQUID_SMALL_CAP = "illiquid_small_cap"
    SURVEILLANCE_LIST = "surveillance_list"
    PRE_POST_VOLUME_SPIKE = "pre_post_volume_spike"
    NOT_SEBI_REGISTERED = "not_sebi_registered"
    VAGUE_CLAIM = "vague_claim"
    DELETED_POST = "deleted_post"


class Mode(StrEnum):
    BASIC = "basic"
    FULL = "full"


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str | None = Field(None, min_length=1, max_length=20_000)
    url: str | None = Field(None, min_length=1, max_length=2_048)
    image_base64: str | None = Field(None, min_length=1, max_length=8_000_000)
    user_guess: SourceLabel | None = None
    user_confidence: int | None = Field(None, ge=50, le=100, strict=True)

    @model_validator(mode="after")
    def one_input(self) -> "VerifyRequest":
        if self.image_base64 is not None:
            if self.text is not None or self.url is not None:
                raise ValueError("Submit a screenshot separately from text or a link.")
        elif self.text is None and self.url is None:
            raise ValueError("Provide a link, pasted text or screenshot.")
        return self


class SourceFacts(BaseModel):
    calls_tracked: int = Field(ge=0)
    correct: int = Field(ge=0)
    deleted: int = Field(ge=0)
    sebi_registered: bool | None
    sebi_reg_no: str | None = None


class SourceView(BaseModel):
    id: UUID
    platform: str
    handle: str
    label: SourceLabel | None
    score: int | None = Field(ge=0, le=100)
    facts: SourceFacts | None
    data_origin: DataOrigin


class ClaimOutcome(BaseModel):
    correct: bool
    method: str
    stock_pct: float | None = None
    index_pct: float | None = None
    data_origin: DataOrigin


class TipFactCode(StrEnum):
    REQUIRED_MOVE_PCT = "required_move_pct"
    MOVE_BASE_RATE = "move_base_rate"
    PRE_POST_RUN_UP_PCT = "pre_post_run_up_pct"
    PRE_POST_VOLUME_RATIO = "pre_post_volume_ratio"
    ILLIQUID_SMALL_CAP = "illiquid_small_cap"
    SURVEILLANCE_LIST = "surveillance_list"
    STOP_DISTANCE_PCT = "stop_distance_pct"
    REWARD_RISK = "reward_risk"


class TipFact(BaseModel):
    code: TipFactCode
    text: str
    value: float | bool | str | None
    as_of: date
    data_origin: DataOrigin


class EnforcementView(BaseModel):
    flag: bool | None = None
    refs: list[dict[str, str]] = Field(default_factory=list)
    data_origin: DataOrigin


class MentionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    url: str
    title: str
    published_at: datetime | None
    platform: str
    fetched_at: datetime
    data_origin: DataOrigin


class ClaimView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tip_facts: list[TipFact] = Field(default_factory=list)
    evidence_start_s: float | None = None
    evidence_end_s: float | None = None
    symbol: str | None
    direction: Direction | None
    entry: float | None
    target: float | None
    stop: float | None
    window_end: date | None
    scorable: bool
    status: ClaimStatus
    data_origin: DataOrigin


class RedFlag(BaseModel):
    code: RedFlagCode
    text: str
    evidence: dict[str, str | int | float | bool | None]
    data_origin: DataOrigin


class VerifyResponse(BaseModel):
    submission_id: UUID
    source: SourceView
    claim: ClaimView
    red_flags: list[RedFlag]
    tip_facts: list[TipFact] = Field(default_factory=list)
    claims: list[ClaimView] = Field(default_factory=list)
    mode: Mode
    extraction_available: bool = True
    data_origin: DataOrigin


class RatingChange(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int = Field(ge=0, le=100)
    label: SourceLabel
    reason: str
    changed_at: datetime
    formula_version: str | None = None
    data_origin: DataOrigin


class SourceResponse(BaseModel):
    source: SourceView
    history: list[RatingChange]
    recent_claims: list[ClaimView]
    enforcement: EnforcementView
    mentions: list[MentionView] = Field(default_factory=list)
    data_origin: DataOrigin


class SubmissionItem(BaseModel):
    submission_id: UUID
    claim: ClaimView
    status: ClaimStatus
    outcome: ClaimOutcome | None
    data_origin: DataOrigin


class SubmissionsResponse(BaseModel):
    items: list[SubmissionItem]
    data_origin: ResponseDataOrigin
    # Pagination cursor, surfaced via the X-Next-Offset header (not in the JSON body).
    next_offset: int | None = Field(default=None, exclude=True)
