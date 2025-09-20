"""Backend client implementations for policy execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict

import httpx

from .config import GatewaySettings


@dataclass
class BackendResult:
    text: str
    metadata: Dict[str, Any]


class BackendClient:
    async def call(self, policy_id: str, payload: Dict[str, Any]) -> BackendResult:  # pragma: no cover - interface
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover - optional override
        return None


class StubBackend(BackendClient):
    async def call(self, policy_id: str, payload: Dict[str, Any]) -> BackendResult:
        await asyncio.sleep(0.05)
        text = f"[policy={policy_id}] response for skill={payload.get('skill')}"
        return BackendResult(text=text, metadata={"source": "stub"})


class HttpBackend(BackendClient):
    def __init__(self, settings: GatewaySettings) -> None:
        if not settings.inference_base_url:
            raise ValueError("INFERENCE_BASE_URL must be configured for HttpBackend")
        self._settings = settings
        self._client = httpx.AsyncClient(base_url=settings.inference_base_url, timeout=20.0)

    async def call(self, policy_id: str, payload: Dict[str, Any]) -> BackendResult:
        headers = {"Content-Type": "application/json"}
        if self._settings.inference_api_key:
            headers["Authorization"] = f"Bearer {self._settings.inference_api_key}"
        body = {
            "policy_id": policy_id,
            "skill": payload.get("skill"),
            "input": payload.get("input"),
            "context": payload.get("context"),
        }
        response = await self._client.post("/v1/infer", json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
        # Accept a couple of common response shapes
        if isinstance(data, dict):
            text = data.get("text") or data.get("output", {}).get("text") or ""
            metadata = data
        else:
            text = str(data)
            metadata = {"raw": data}
        return BackendResult(text=text, metadata=metadata)

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["BackendClient", "BackendResult", "StubBackend", "HttpBackend"]
