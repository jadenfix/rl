"""Backend client stubs for policy execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class BackendResult:
    text: str
    metadata: Dict[str, Any]


class BackendClient:
    async def call(self, policy_id: str, payload: Dict[str, Any]) -> BackendResult:  # pragma: no cover - interface
        raise NotImplementedError


class StubBackend(BackendClient):
    async def call(self, policy_id: str, payload: Dict[str, Any]) -> BackendResult:
        await asyncio.sleep(0.05)
        text = f"[policy={policy_id}] response for skill={payload.get('skill')}"
        return BackendResult(text=text, metadata={"source": "stub"})


__all__ = ["BackendClient", "BackendResult", "StubBackend"]
