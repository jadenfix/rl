from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from . import schemas
from .pii import build_scrubber
from .storage import PersistenceLayer, PersistenceSettings

logger = logging.getLogger("collector")
logging.basicConfig(level=logging.INFO)

settings = PersistenceSettings.from_env()
storage = PersistenceLayer(settings=settings)
scrubber = build_scrubber(
    enabled=settings.pii_scrub_enabled,
    allowlist=settings.pii_tenant_allowlist,
    redaction_token=settings.pii_redaction_token,
)

app = FastAPI(title="RLaaS Telemetry Collector", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def _scrub_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    tenant_id = payload.get("tenant_id") if isinstance(payload, dict) else None
    return scrubber.scrub(payload, tenant_id=tenant_id)


@app.get("/healthz")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "collector"}


@app.get("/metrics")
def metrics() -> Response:
    body = "collector_ingest_total 0\n"
    return Response(content=body, media_type="text/plain; version=0.0.4")


@app.post("/v1/interaction.create", status_code=202)
def interaction_create(event: schemas.InteractionCreate) -> Dict[str, str]:
    cleaned = _scrub_payload(event.model_dump())
    try:
        storage.write_event(event_type="interaction.create", payload=cleaned)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to persist interaction.create")
        raise HTTPException(status_code=500, detail="Persistence failure") from exc
    logger.info("interaction.create %s", cleaned)
    return {"status": "accepted"}


@app.post("/v1/interaction.output", status_code=202)
def interaction_output(event: schemas.InteractionOutput) -> Dict[str, str]:
    cleaned = _scrub_payload(event.model_dump())
    try:
        storage.write_event(event_type="interaction.output", payload=cleaned)
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to persist interaction.output")
        raise HTTPException(status_code=500, detail="Persistence failure") from exc
    logger.info("interaction.output %s", cleaned)
    return {"status": "accepted"}


@app.post("/v1/feedback.submit", status_code=202)
def feedback_submit(event: schemas.FeedbackSubmit) -> Dict[str, str]:
    cleaned = _scrub_payload(event.model_dump())
    try:
        storage.write_event(event_type="feedback.submit", payload=cleaned)
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to persist feedback.submit")
        raise HTTPException(status_code=500, detail="Persistence failure") from exc
    logger.info("feedback.submit %s", cleaned)
    return {"status": "accepted"}


@app.post("/v1/task_result", status_code=202)
def task_result(event: schemas.TaskResult) -> Dict[str, str]:
    cleaned = _scrub_payload(event.model_dump())
    try:
        storage.write_event(event_type="task.result", payload=cleaned)
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to persist task.result")
        raise HTTPException(status_code=500, detail="Persistence failure") from exc
    logger.info("task.result %s", cleaned)
    return {"status": "accepted"}


@app.post("/v1/validate", status_code=200)
def validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Utility endpoint to check arbitrary payloads against supported event schemas."""
    for model in (
        schemas.InteractionCreate,
        schemas.InteractionOutput,
        schemas.FeedbackSubmit,
        schemas.TaskResult,
    ):
        try:
            model.model_validate(payload)  # type: ignore[attr-defined]
            return {"event_type": model.__name__, "valid": True}
        except ValidationError:
            continue
    raise HTTPException(status_code=400, detail="Payload does not match any collector schema")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    storage.close()
