from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Stub Inference Runner", version="0.1.0")


class InferencePayload(BaseModel):
    policy_id: str
    skill: str
    input: dict
    context: dict | None = None


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok", "service": "inference"}


@app.post("/v1/infer")
async def infer(payload: InferencePayload) -> dict:
    text = f"[{payload.policy_id}] {payload.input.get('text', '')}".strip()
    return {
        "text": text,
        "costs": {"tokens_in": len(payload.input.get('text', '')), "tokens_out": len(text)},
        "metadata": {"runner": "stub", "skill": payload.skill},
    }
