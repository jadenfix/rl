"""Python client for the RLaaS telemetry collector."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx

from .buffer import OfflineBuffer
from .config import ClientConfig


class TelemetryClient:
    def __init__(self, config: ClientConfig, *, transport: Optional[httpx.BaseTransport] = None) -> None:
        self._config = config
        self._client = httpx.Client(base_url=config.base_url, timeout=config.timeout, transport=transport)
        self._buffer = OfflineBuffer(config.offline_path)

    def __enter__(self) -> "TelemetryClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "User-Agent": self._config.user_agent,
            "Content-Type": "application/json",
        }
        headers.update(self._config.headers)
        return headers

    def _prepare_payload(self, payload: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[str]]:
        outgoing = dict(payload)
        idempotency_key = outgoing.get("idempotency_key")
        if not idempotency_key and self._config.auto_idempotency:
            idempotency_key = uuid4().hex
            outgoing["idempotency_key"] = idempotency_key
        return outgoing, idempotency_key

    def _post(self, path: str, payload: Dict[str, Any]) -> None:
        outgoing, idempotency_key = self._prepare_payload(payload)
        headers = self._headers()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        body = json.dumps(outgoing, separators=(",", ":"))
        attempt = 0
        while attempt <= self._config.max_retries:
            try:
                response = self._client.post(path, content=body, headers=headers)
                response.raise_for_status()
                return
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                attempt += 1
                if attempt > self._config.max_retries:
                    self._buffer.append({"path": path, "payload": outgoing})
                    raise
                sleep_for = self._config.backoff_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_for)

    def log_interaction(self, event: Dict[str, Any]) -> None:
        self._post("/v1/interaction.create", event)

    def log_output(self, event: Dict[str, Any]) -> None:
        self._post("/v1/interaction.output", event)

    def submit_feedback(self, event: Dict[str, Any]) -> None:
        self._post("/v1/feedback.submit", event)

    def log_task_result(self, event: Dict[str, Any]) -> None:
        self._post("/v1/task_result", event)

    def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._client.post(
            "/v1/validate",
            content=json.dumps(payload, separators=(",", ":")),
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def flush_offline(self) -> int:
        if not self._buffer.enabled():
            return 0

        def sender(item: Dict[str, Any]) -> None:
            self._post(item["path"], item["payload"])

        return self._buffer.replay(sender)

    def close(self) -> None:
        self._client.close()


__all__ = ["TelemetryClient"]
