"""FastAPI-based inference gateway skeleton."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Tuple

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest

from .backends import BackendClient, BackendResult, StubBackend
from .logging import build_shadow_log, log_shadow_results
from .config import GatewaySettings, settings
from .models import HealthResponse, InferenceRequest, InferenceResponse, PolicyDecision, PolicyListResponse
from .policy import PolicyStore
from .router import PolicyRouter

logger = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RLaaS Inference Gateway", version="0.2.0")

REQUEST_COUNTER = Counter("gateway_inference_requests_total", "Total inference requests", ["tenant", "skill"])
SHADOW_GAUGE = Gauge("gateway_shadow_candidates", "Number of shadow policies sampled")
REQUEST_LATENCY = Histogram("gateway_inference_latency_seconds", "Gateway inference latency", ["policy_id"])


_store = PolicyStore(settings=settings)
_router = PolicyRouter(settings=settings)
_backend = StubBackend()


def get_store() -> PolicyStore:
    return _store


def get_router() -> PolicyRouter:
    return _router


def get_backend() -> BackendClient:
    return _backend


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
async def infer(
    request: InferenceRequest,
    store: PolicyStore = Depends(get_store),
    router: PolicyRouter = Depends(get_router),
    backend: BackendClient = Depends(get_backend),
) -> InferenceResponse:
    policies = store.list_policies(request.tenant_id, request.skill)
    if not policies:
        raise HTTPException(status_code=404, detail="No policies available for tenant")

    decision = router.choose(policies)
    REQUEST_COUNTER.labels(tenant=request.tenant_id, skill=request.skill).inc()
    SHADOW_GAUGE.set(len(decision.shadow_candidates))

    payload = {
        "tenant_id": request.tenant_id,
        "skill": request.skill,
        "input": request.input,
        "context": request.context,
    }

    main_result, shadow_results = await _execute_policies(backend, decision, payload)

    if shadow_results:
        shadow_payload = build_shadow_log(request, decision, shadow_results)
        log_shadow_results(shadow_payload)

    response = InferenceResponse(
        decision=decision,
        output={"text": main_result.text, "metadata": main_result.metadata},
        version={
            "policy_id": decision.selected.policy_id,
            "base_model": decision.selected.base_model,
            "router_reason": decision.reason,
            "shadow_candidates": [p.policy_id for p in decision.shadow_candidates],
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


async def _execute_policies(
    backend: BackendClient,
    decision: PolicyDecision,
    payload: Dict[str, Any],
) -> Tuple[BackendResult, List[BackendResult]]:
    shadow_tasks = []
    for policy in decision.shadow_candidates:
        shadow_tasks.append(backend.call(policy.policy_id, payload))

    with REQUEST_LATENCY.labels(policy_id=decision.selected.policy_id).time():
        main_result = await backend.call(decision.selected.policy_id, payload)

    shadow_results = []
    if shadow_tasks:
        shadow_results = await asyncio.gather(*shadow_tasks, return_exceptions=False)
    return main_result, shadow_results


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
