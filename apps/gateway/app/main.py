"""FastAPI-based inference gateway skeleton."""

from __future__ import annotations

import logging
import random
from typing import Dict

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, generate_latest

from .config import GatewaySettings, settings
from .models import HealthResponse, InferenceRequest, InferenceResponse, PolicyListResponse
from .policy import PolicyStore
from .router import PolicyRouter

logger = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RLaaS Inference Gateway", version="0.2.0")

REQUEST_COUNTER = Counter("gateway_inference_requests_total", "Total inference requests", ["tenant", "skill"])
SHADOW_GAUGE = Gauge("gateway_shadow_candidates", "Number of shadow policies sampled")


_store = PolicyStore(settings=settings)
_router = PolicyRouter(settings=settings)


def get_store() -> PolicyStore:
    return _store


def get_router() -> PolicyRouter:
    return _router


@app.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    data = generate_latest()
    return PlainTextResponse(data, media_type="text/plain; version=0.0.4")


@app.get("/v1/policies/{tenant_id}", response_model=PolicyListResponse)
def list_policies(tenant_id: str, skill: str | None = None, store: PolicyStore = Depends(get_store)):  # type: ignore[assignment]
    policies = store.list_policies(tenant_id=tenant_id, skill=skill)
    return PolicyListResponse(tenant_id=tenant_id, skill=skill, policies=policies)


@app.post("/v1/infer", response_model=InferenceResponse)
def infer(
    request: InferenceRequest,
    store: PolicyStore = Depends(get_store),
    router: PolicyRouter = Depends(get_router),
) -> InferenceResponse:
    policies = store.list_policies(request.tenant_id, request.skill)
    if not policies:
        raise HTTPException(status_code=404, detail="No policies available for tenant")

    decision = router.choose(policies)
    REQUEST_COUNTER.labels(tenant=request.tenant_id, skill=request.skill).inc()
    SHADOW_GAUGE.set(len(decision.shadow_candidates))

    # Placeholder inference call – replace with actual model invocation / streaming.
    synthetic_text = _stub_generate_text(request)

    response = InferenceResponse(
        decision=decision,
        output={"text": synthetic_text, "annotations": {"source": "stub"}},
        version={
            "policy_id": decision.selected.policy_id,
            "base_model": decision.selected.base_model,
            "router_reason": decision.reason,
        },
    )
    logger.info(
        "tenant=%s skill=%s selected_policy=%s shadow=%s",
        request.tenant_id,
        request.skill,
        decision.selected.policy_id,
        [p.policy_id for p in decision.shadow_candidates],
    )
    return response


def _stub_generate_text(request: InferenceRequest) -> str:
    prompt = request.input.get("text") if isinstance(request.input, dict) else None
    suffix = "..." if prompt else ""
    return f"[stubbed completion for {request.skill}{suffix}]"


@app.on_event("startup")
def on_startup() -> None:
    # Warm the store connection pool.
    _store.open()
    logger.info("Gateway startup complete (shadow rate=%.2f)", settings.shadow_sampling_rate)


@app.on_event("shutdown")
def on_shutdown() -> None:
    _store.close()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
