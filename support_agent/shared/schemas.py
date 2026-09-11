"""Structured requests, model replies and support decisions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class HistoryMessage(StrictModel):
    role: Literal["customer", "agent"]
    text: str = Field(min_length=1)


class SupportRequest(StrictModel):
    company_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    conversation_history: list[HistoryMessage] = Field(default_factory=list)
    channel: str = "web"


class Classification(StrictModel):
    intent: str | None
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class ReplyDraft(StrictModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str]


class ReplyCheck(StrictModel):
    grounded: bool
    safe: bool
    reason: str = Field(min_length=1)


class SupportResult(StrictModel):
    company_id: str
    intent: str | None
    intent_confidence: float
    draft_reply: str
    evidence_ids: list[str]
    retrieved_examples: list[dict]
    decision: Literal["auto_handle", "escalate"]
    decision_reason: str
    safety_flags: list[str]
    reply_status: Literal["generated", "safe_fallback"]


class JudgeScores(StrictModel):
    scores: dict[str, int]
    explanations: dict[str, str]
