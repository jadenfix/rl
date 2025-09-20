"""Dual-run logging utilities for shadow policies."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from .backends import BackendResult
from .models import InferenceRequest, PolicyDecision

logger = logging.getLogger("gateway.shadow")


def build_shadow_log(
    request: InferenceRequest,
    decision: PolicyDecision,
    shadow_results: List[BackendResult],
) -> Dict[str, Any]:
    entries = []
    for policy, result in zip(decision.shadow_candidates, shadow_results):
        entries.append(
            {
                "policy_id": policy.policy_id,
                "status": policy.status,
                "base_model": policy.base_model,
                "output": result.text,
                "metadata": result.metadata,
            }
        )
    return {
        "tenant_id": request.tenant_id,
        "skill": request.skill,
        "interaction_input": request.input,
        "decision": {
            "selected": decision.selected.policy_id,
            "reason": decision.reason,
        },
        "shadow_entries": entries,
    }


def log_shadow_results(payload: Dict[str, Any]) -> None:
    logger.info(json.dumps(payload))


__all__ = ["build_shadow_log", "log_shadow_results"]
