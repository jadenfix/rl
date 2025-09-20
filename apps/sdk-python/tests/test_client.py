from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import httpx
import pytest

from rl_sdk.client import TelemetryClient
from rl_sdk.config import ClientConfig


@pytest.fixture()
def client(tmp_path: Path) -> TelemetryClient:
    buffer_path = tmp_path / "buffer.ndjson"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert "Authorization" in request.headers
        assert request.headers["User-Agent"].startswith("rl-sdk-python")
        assert "Idempotency-Key" in request.headers
        assert payload.get("idempotency_key") == request.headers["Idempotency-Key"]
        return httpx.Response(202, json={"status": "accepted", "echo": payload})

    transport = httpx.MockTransport(handler)
    cfg = ClientConfig(base_url="https://api.example.com", api_key="test-key", offline_path=str(buffer_path))
    return TelemetryClient(cfg, transport=transport)


def test_log_interaction_success(client: TelemetryClient) -> None:
    payload = {
        "tenant_id": "acme",
        "user_id": "user",
        "skill": "support",
        "input": {"text": "hello"},
        "context": {},
        "version": {"policy_id": "policy@v1", "base_model": "model"},
        "timings": {"ms_total": 10},
        "costs": {"tokens_in": 1, "tokens_out": 2},
    }
    client.log_interaction(payload)


def test_retry_and_buffer(tmp_path: Path) -> None:
    attempts = {"count": 0, "keys": []}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        attempts["keys"].append(request.headers.get("Idempotency-Key"))
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(handler)
    buffer_path = tmp_path / "buffer.ndjson"
    cfg = ClientConfig(
        base_url="https://api.example.com",
        api_key="test",
        offline_path=str(buffer_path),
        max_retries=1,
        backoff_seconds=0,
    )
    client = TelemetryClient(cfg, transport=transport)

    payload = {
        "tenant_id": "acme",
        "interaction_id": "123",
        "output": {"text": "hi"},
        "timings": {"ms_total": 1},
        "costs": {"tokens_in": 1, "tokens_out": 1},
        "version": {"policy_id": "policy@v1", "base_model": "model"},
    }

    with pytest.raises(httpx.HTTPStatusError):
        client.log_output(payload)

    assert buffer_path.exists()
    buffered = buffer_path.read_text().strip()
    assert "/v1/interaction.output" in buffered
    assert attempts["count"] == 2
    assert attempts["keys"][0] == attempts["keys"][1]


def test_flush_replays_buffer(tmp_path: Path) -> None:
    # First call fails and buffers, second transport succeeds when flushing
    fail_first = {"count": 0}

    def failing_handler(request: httpx.Request) -> httpx.Response:
        fail_first["count"] += 1
        return httpx.Response(500, text="boom")

    fail_transport = httpx.MockTransport(failing_handler)
    buffer_path = tmp_path / "buffer.ndjson"
    cfg = ClientConfig(
        base_url="https://api.example.com",
        api_key="test",
        offline_path=str(buffer_path),
        max_retries=0,
    )
    client = TelemetryClient(cfg, transport=fail_transport)

    payload = {
        "tenant_id": "acme",
        "interaction_id": "1",
        "label": {"correct": True},
    }

    with pytest.raises(httpx.HTTPStatusError):
        client.log_task_result(payload)

    assert buffer_path.exists()
    buffered = json.loads(buffer_path.read_text().strip().splitlines()[0])
    assert "idempotency_key" in buffered["payload"]

    def success_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Idempotency-Key") == json.loads(request.content)["idempotency_key"]
        return httpx.Response(202)

	success_transport = httpx.MockTransport(success_handler)
	client._client = httpx.Client(base_url=cfg.base_url, timeout=cfg.timeout, transport=success_transport)
	flushed = client.flush_offline()
	assert flushed == 1


def test_disable_auto_idempotency(tmp_path: Path) -> None:
	headers: list[Optional[str]] = []

	def handler(request: httpx.Request) -> httpx.Response:
		headers.append(request.headers.get("Idempotency-Key"))
		return httpx.Response(202)

	transport = httpx.MockTransport(handler)
	cfg = ClientConfig(
		base_url="https://api.example.com",
		api_key="test",
		max_retries=0,
		auto_idempotency=False,
	)
	client = TelemetryClient(cfg, transport=transport)
	client.submit_feedback({"tenant_id": "acme", "interaction_id": "1"})
	assert headers == [None]
