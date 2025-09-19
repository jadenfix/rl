"""Python client for the RLaaS telemetry collector."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

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

    def _post(self, path: str, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"))
        attempt = 0
        while attempt <= self._config.max_retries:
            try:
                response = self._client.post(path, content=body, headers=self._headers())
                response.raise_for_status()
                return
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                attempt += 1
                if attempt > self._config.max_retries:
                    self._buffer.append({"path": path, "payload": payload})
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
