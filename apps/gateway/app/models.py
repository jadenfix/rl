"""Pydantic models for the inference gateway."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    skill: str = Field(..., min_length=1)
    input: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    version: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class Policy(BaseModel):
    policy_id: str
    status: str
    base_model: str
    prompt_version: Optional[str] = None
    adapter_ref: Optional[str] = None


class PolicyDecision(BaseModel):
    selected: Policy
    shadow_candidates: List[Policy] = Field(default_factory=list)
    reason: str


class InferenceResponse(BaseModel):
    decision: PolicyDecision
    output: Dict[str, Any]
    version: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "gateway"


class PolicyListResponse(BaseModel):
    tenant_id: str
    skill: Optional[str]
    policies: List[Policy]
