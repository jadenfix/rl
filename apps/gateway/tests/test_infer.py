from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest
from httpx import AsyncClient, MockTransport, Request, Response

from apps.gateway.app.main import app, _backend, _telemetry, _store
from apps.gateway.app.config import GatewaySettings
from apps.gateway.app.backends import HttpBackend
from apps.gateway.app.telemetry import CollectorClient
from apps.gateway.app.policy import PolicyStore
from apps.gateway.app.router import PolicyRouter
from apps.gateway.app.models import Policy


@pytest.fixture(autouse=True)
async def setup_policy_store(monkeypatch):
    # Mock store to return deterministic policies
    class DummyStore(PolicyStore):
        def __init__(self):
            pass

        def list_policies(self, tenant_id: str, skill: str | None = None):  # type: ignore[override]
            return [
                Policy(policy_id="support@v1", status="active", base_model="llama"),
                Policy(policy_id="support@shadow", status="shadow", base_model="llama"),
            ]

    monkeypatch.setattr("apps.gateway.app.main._store", DummyStore())
    monkeypatch.setattr("apps.gateway.app.main._router", PolicyRouter(settings=_store.settings if hasattr(_store, "settings") else None))
    yield


@pytest.fixture(autouse=True)
async def mock_backend(monkeypatch):
    async def handler(request: Request) -> Response:
        data = request.json()
        text = f"{data['policy_id']}::{data['input']['text']}"
        return Response(200, json={"text": text, "costs": {"tokens_in": 1, "tokens_out": 2}})

    transport = MockTransport(handler)
    backend = HttpBackend(GatewaySettings(
        postgres_dsn="postgresql://test",
        collector_url="http://collector",
        collector_api_key="",
        inference_base_url="http://inference",
        inference_api_key="",
        use_stub_backend=False,
    ))
    backend._client = AsyncClient(transport=transport, base_url="http://inference")
    monkeypatch.setattr("apps.gateway.app.main._backend", backend)
    yield
    await backend.close()


@pytest.fixture(autouse=True)
async def mock_collector(monkeypatch):
    class DummyCollector(CollectorClient):
        def __init__(self):
            self.logged: list[Dict[str, Any]] = []

        async def log_output(self, payload: Dict[str, Any]) -> None:
            self.logged.append(payload)

    collector = DummyCollector()
    monkeypatch.setattr("apps.gateway.app.main._telemetry", collector)
    yield collector


@pytest.mark.asyncio
async def test_infer_dual_run(mock_collector):
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/infer",
            json={
                "tenant_id": "acme",
                "skill": "support",
                "input": {"text": "hello"},
            },
        )
        response.raise_for_status()
        data = response.json()
        assert data["output"]["text"].startswith("support@v1")

        # Ensure shadow output logged
        shadow_entries = [event for event in mock_collector.logged if event["version"].get("status") == "shadow"]
        assert shadow_entries
        comparison = shadow_entries[0]["version"].get("comparison")
        assert comparison is not None
        assert "match" in comparison
