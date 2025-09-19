"""Pydantic models describing telemetry events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, conint, constr


NonEmptyStr = constr(min_length=1)
NonNegativeInt = conint(ge=0)


class RetrievalChunk(BaseModel):
    id: NonEmptyStr
    text: NonEmptyStr
    score: Optional[float] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InteractionInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: NonEmptyStr
    attachments: Optional[List[str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InteractionContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    retrieval_chunks: Optional[List[RetrievalChunk]] = None
    customer_tier: Optional[str] = None
    sla_mins: Optional[NonNegativeInt] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VersionInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    policy_id: NonEmptyStr
    base_model: NonEmptyStr
    adapter: Optional[str] = None


class TimingInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    ms_total: NonNegativeInt
    ms_decode: Optional[NonNegativeInt] = None


class CostInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    tokens_in: NonNegativeInt
    tokens_out: NonNegativeInt
    dollars: Optional[float] = Field(default=None, ge=0)


class InteractionCreate(BaseModel):
    tenant_id: NonEmptyStr
    user_id: NonEmptyStr
    skill: NonEmptyStr
    input: InteractionInput
    context: InteractionContext = Field(default_factory=InteractionContext)
    version: VersionInfo
    timings: TimingInfo
    costs: CostInfo
    idempotency_key: Optional[NonEmptyStr] = None
    created_at: Optional[datetime] = None


class ToolCall(BaseModel):
    tool_name: NonEmptyStr
    arguments: Dict[str, Any]
    status: Optional[str] = None
    latency_ms: Optional[NonNegativeInt] = None


class Citation(BaseModel):
    chunk_id: NonEmptyStr
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class InteractionOutputPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: NonEmptyStr
    tool_calls: Optional[List[ToolCall]] = None
    citations: Optional[List[Citation]] = None


class InteractionOutput(BaseModel):
    tenant_id: NonEmptyStr
    interaction_id: NonEmptyStr
    output: InteractionOutputPayload
    timings: TimingInfo
    costs: CostInfo
    version: VersionInfo
    trace_id: Optional[str] = None
    idempotency_key: Optional[NonEmptyStr] = None
    created_at: Optional[datetime] = None


class ExplicitFeedback(BaseModel):
    thumb: Optional[Literal[-1, 1]] = None
    rating: Optional[conint(strict=True, ge=1, le=5)] = None
    comment: Optional[str] = None


class ImplicitFeedback(BaseModel):
    edited_text: Optional[str] = None
    sent: Optional[bool] = None
    time_to_send_ms: Optional[NonNegativeInt] = None
    escalated: Optional[bool] = None
    follow_up_count: Optional[NonNegativeInt] = None


class FeedbackSubmit(BaseModel):
    tenant_id: NonEmptyStr
    interaction_id: NonEmptyStr
    explicit: Optional[ExplicitFeedback] = None
    implicit: Optional[ImplicitFeedback] = None
    labels: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[NonEmptyStr] = None
    created_at: Optional[datetime] = None


class TaskLabel(BaseModel):
    correct: Optional[bool] = None
    f1: Optional[float] = Field(default=None, ge=0, le=1)
    resolved: Optional[bool] = None
    kpi_delta: Optional[float] = None


class TaskResult(BaseModel):
    tenant_id: NonEmptyStr
    interaction_id: NonEmptyStr
    label: TaskLabel
    observed_at: Optional[datetime] = None
    note: Optional[str] = None
    idempotency_key: Optional[NonEmptyStr] = None
    created_at: Optional[datetime] = None


TelemetryEvent = InteractionCreate | InteractionOutput | FeedbackSubmit | TaskResult
