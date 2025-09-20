"""FastAPI-based inference gateway skeleton."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest

from .archive import ShadowLogWriter
from .backends import BackendClient, BackendResult, HttpBackend, StubBackend
from .config import GatewaySettings, settings
from .logging import build_shadow_log, log_shadow_results
from .models import (
    HealthResponse,
    InferenceRequest,
    InferenceResponse,
    PolicyDecision,
    PolicyListResponse,
)
from .policy import PolicyStore
from .router import PolicyRouter
from .telemetry import CollectorClient

logger = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RLaaS Inference Gateway", version="0.3.0")

REQUEST_COUNTER = Counter("gateway_inference_requests_total", "Total inference requests", ["tenant", "skill"])
SHADOW_GAUGE = Gauge("gateway_shadow_candidates", "Number of shadow policies sampled")
REQUEST_LATENCY = Histogram("gateway_inference_latency_seconds", "Gateway inference latency", ["policy_id"])
SHADOW_COMPARISON_COUNTER = Counter(
    "gateway_shadow_comparisons_total",
    "Shadow comparison outcomes",
    ["selected_policy", "shadow_policy", "match"],
)

_store = PolicyStore(settings=settings)
_router = PolicyRouter(settings=settings)
_backend: BackendClient = StubBackend() if settings.use_stub_backend else HttpBackend(settings=settings)
_telemetry = CollectorClient(settings=settings)
_shadow_writer = ShadowLogWriter.from_path(settings.shadow_log_path)


def get_store() -> PolicyStore:
    return _store


def get_router() -> PolicyRouter:
    return _router


def get_backend() -> BackendClient:
    return _backend


def get_telemetry() -> CollectorClient:
    return _telemetry


@app.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    data = generate_latest()
    return PlainTextResponse(data, media_type="text/plain; version=0.0.4")


@app.get("/debug/shadow-log")
def shadow_log(limit: int = 50) -> Dict[str, Any]:
    if _shadow_writer is None:
        raise HTTPException(status_code=404, detail="Shadow log disabled")
    safe_limit = max(1, min(limit, 200))
    entries = _shadow_writer.tail(safe_limit)
    return {"entries": entries, "limit": safe_limit}


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
    telemetry: CollectorClient = Depends(get_telemetry),
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

    interaction_id = (
        request.interaction_id
        or (request.metadata or {}).get("interaction_id")
        or uuid4().hex
    )

    main_result, main_latency, shadow_pairs = await _execute_policies(backend, decision, payload)

    if shadow_pairs:
        shadow_payload = build_shadow_log(request, decision, [result for _, result, _ in shadow_pairs])
        log_shadow_results(shadow_payload)

    await _log_outputs(
        telemetry=telemetry,
        request=request,
        decision=decision,
        interaction_id=interaction_id,
        main_result=main_result,
        main_latency=main_latency,
        shadow_pairs=shadow_pairs,
    )

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
) -> Tuple[BackendResult, float, List[Tuple[str, BackendResult, float]]]:
    async def call_policy(policy_id: str) -> Tuple[BackendResult, float]:
        start = time.perf_counter()
        result = await backend.call(policy_id, payload)
        elapsed = time.perf_counter() - start
        return result, elapsed

    shadow_tasks = [call_policy(policy.policy_id) for policy in decision.shadow_candidates]

    with REQUEST_LATENCY.labels(policy_id=decision.selected.policy_id).time():
        main_result, main_latency = await call_policy(decision.selected.policy_id)

    shadow_pairs: List[Tuple[str, BackendResult, float]] = []
    if shadow_tasks:
        shadow_results = await asyncio.gather(*shadow_tasks, return_exceptions=False)
        for policy, (result, latency) in zip(decision.shadow_candidates, shadow_results):
            shadow_pairs.append((policy.policy_id, result, latency))

    return main_result, main_latency, shadow_pairs


async def _log_outputs(
    *,
    telemetry: CollectorClient,
    request: InferenceRequest,
    decision: PolicyDecision,
    interaction_id: str,
    main_result: BackendResult,
    main_latency: float,
    shadow_pairs: List[Tuple[str, BackendResult, float]],
) -> None:
    main_event = _build_output_event(
        tenant_id=request.tenant_id,
        interaction_id=interaction_id,
        result=main_result,
        policy_id=decision.selected.policy_id,
        base_model=decision.selected.base_model,
        status=decision.reason,
        latency=main_latency,
        metadata=request.metadata,
    )
    await telemetry.log_output(main_event)

    if not shadow_pairs:
        return

    await asyncio.gather(
        *[
            telemetry.log_output(
                _build_output_event(
                    tenant_id=request.tenant_id,
                    interaction_id=interaction_id,
                    result=result,
                    policy_id=policy_id,
                    base_model=decision.selected.base_model,
                    status="shadow",
                    latency=latency,
                    metadata=request.metadata,
                    shadow_of=decision.selected.policy_id,
                    comparison=_compare_outputs(
                        main_result,
                        result,
                        selected_policy=decision.selected.policy_id,
                        shadow_policy=policy_id,
                    ),
                )
            )
            for policy_id, result, latency in shadow_pairs
        ],
        return_exceptions=False,
    )

    if _shadow_writer is not None:
        entries = []
        for policy_id, result, latency in shadow_pairs:
            comparison = _compare_outputs(
                main_result,
                result,
                selected_policy=decision.selected.policy_id,
                shadow_policy=policy_id,
            )
            entries.append(
                {
                    "tenant_id": request.tenant_id,
                    "interaction_id": interaction_id,
                    "skill": request.skill,
                    "selected_policy": decision.selected.policy_id,
                    "shadow_policy": policy_id,
                    "latency_ms": int(latency * 1000),
                    "output": result.text,
                    "metadata": result.metadata,
                    "comparison": comparison,
                }
            )
        await _shadow_writer.append(entries)


def _build_output_event(
    *,
    tenant_id: str,
    interaction_id: str,
    result: BackendResult,
    policy_id: str,
    base_model: str,
    status: str,
    latency: float,
    metadata: Dict[str, Any] | None,
    shadow_of: str | None = None,
    comparison: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    costs = result.metadata.get("costs") if isinstance(result.metadata, dict) else None
    if not isinstance(costs, dict):
        costs = {"tokens_in": 0, "tokens_out": 0}
    event: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "interaction_id": interaction_id,
        "output": {"text": result.text, "metadata": result.metadata},
        "timings": {"ms_total": max(int(latency * 1000), 1)},
        "costs": costs,
        "version": {
            "policy_id": policy_id,
            "base_model": base_model,
            "status": status,
        },
        "idempotency_key": f"{interaction_id}:{policy_id}:{status}",
    }
    if metadata:
        event["metadata"] = metadata
    if shadow_of:
        event["version"]["shadow_of"] = shadow_of
    if comparison:
        event["version"]["comparison"] = comparison
    return event


def _compare_outputs(
    main: BackendResult,
    shadow: BackendResult,
    *,
    selected_policy: str,
    shadow_policy: str,
) -> Dict[str, Any]:
    match = main.text.strip() == shadow.text.strip()
    SHADOW_COMPARISON_COUNTER.labels(
        selected_policy=selected_policy,
        shadow_policy=shadow_policy,
        match=str(match).lower(),
    ).inc()
    length_delta = len(shadow.text) - len(main.text)
    return {
        "match": match,
        "length_delta": length_delta,
    }


@app.on_event("startup")
def on_startup() -> None:
    _store.open()
    logger.info(
        "Gateway startup complete (shadow rate=%.2f, collector=%s)",
        settings.shadow_sampling_rate,
        settings.collector_url,
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    _store.close()
    await _backend.close()
    await _telemetry.close()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
