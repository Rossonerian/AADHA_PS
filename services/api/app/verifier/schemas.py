"""Verifier requests and responses. Claim prices describe the submitted tip only."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
        if (
            sum(value is not None for value in (self.text, self.url, self.image_base64))
            != 1
        ):
            raise ValueError("Provide exactly one of url, text or image_base64.")
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


class ClaimView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
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
    mode: Mode
    data_origin: DataOrigin


class RatingChange(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int = Field(ge=0, le=100)
    label: SourceLabel
    reason: str
    changed_at: datetime
    data_origin: DataOrigin


class SourceResponse(BaseModel):
    source: SourceView
    history: list[RatingChange]
    recent_claims: list[ClaimView]


class SubmissionItem(BaseModel):
    submission_id: UUID
    claim: ClaimView
    status: ClaimStatus
    outcome: ClaimOutcome | None
    data_origin: DataOrigin


class SubmissionsResponse(BaseModel):
    items: list[SubmissionItem]
