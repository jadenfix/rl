"""Async collector client for inference logging."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .config import GatewaySettings

logger = logging.getLogger("gateway.telemetry")


class CollectorClient:
    def __init__(self, settings: GatewaySettings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(base_url=settings.collector_url, timeout=5.0)

    async def log_output(self, payload: Dict[str, Any]) -> None:
        await self._post("/v1/interaction.output", payload)

    async def _post(self, path: str, payload: Dict[str, Any]) -> None:
        headers = {
            "Content-Type": "application/json",
        }
        if self._settings.collector_api_key:
            headers["Authorization"] = f"Bearer {self._settings.collector_api_key}"
        response = await self._client.post(path, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - external failures
            logger.error("Collector request failed status=%s body=%s", response.status_code, response.text)
            raise exc

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["CollectorClient"]
