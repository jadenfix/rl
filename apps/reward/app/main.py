"""Deterministic edit-similarity reward HTTP service."""

from __future__ import annotations

from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from typing import Any


MAX_BODY_BYTES = 65_536
MAX_TEXT_CHARS = 2_000
SCORE_PATH = "/v1/rewards/edit-similarity"

REQUESTS: Counter[str] = Counter(
    health=0,
    not_found=0,
    payload_too_large=0,
    success=0,
    validation_error=0,
)


def levenshtein_distance(left: str, right: str) -> int:
    """Return the Unicode code-point Levenshtein distance."""

    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def score_edit_similarity(candidate: str, edited: str) -> dict[str, Any]:
    distance = levenshtein_distance(candidate, edited)
    scale = max(len(candidate), len(edited))
    score = 1.0 if scale == 0 else 1.0 - (distance / scale)
    return {
        "metric": "normalized_levenshtein_similarity",
        "score": score,
        "distance": distance,
        "candidate_length": len(candidate),
        "edited_length": len(edited),
    }


def validate_payload(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    expected = {"candidate", "edited"}
    unknown = sorted(set(payload) - expected)
    missing = sorted(expected - set(payload))
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")
    for field in ("candidate", "edited"):
        value = payload[field]
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        if len(value) > MAX_TEXT_CHARS:
            raise ValueError(f"{field} exceeds {MAX_TEXT_CHARS} characters")
    return payload["candidate"], payload["edited"]


def metrics_text() -> str:
    lines = [
        "# HELP reward_requests_total Reward HTTP requests by outcome.",
        "# TYPE reward_requests_total counter",
    ]
    for outcome in sorted(REQUESTS):
        lines.append(f'reward_requests_total{{outcome="{outcome}"}} {REQUESTS[outcome]}')
    return "\n".join(lines) + "\n"


class RewardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            REQUESTS["health"] += 1
            self._write_json(200, {"status": "ok", "service": "reward"})
        elif self.path == "/metrics":
            self._write_response(200, metrics_text(), "text/plain; version=0.0.4")
        else:
            REQUESTS["not_found"] += 1
            self._write_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != SCORE_PATH:
            REQUESTS["not_found"] += 1
            self._write_json(404, {"error": "not_found"})
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            REQUESTS["validation_error"] += 1
            self._write_json(415, {"error": "content_type_must_be_application_json"})
            return

        raw_length = self.headers.get("Content-Length")
        try:
            content_length = int(raw_length) if raw_length is not None else -1
        except ValueError:
            content_length = -1
        if content_length < 0:
            REQUESTS["validation_error"] += 1
            self._write_json(411, {"error": "valid_content_length_required"})
            return
        if content_length > MAX_BODY_BYTES:
            REQUESTS["payload_too_large"] += 1
            self.close_connection = True
            self._write_json(413, {"error": "payload_too_large", "max_bytes": MAX_BODY_BYTES})
            return

        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            REQUESTS["validation_error"] += 1
            self._write_json(400, {"error": "malformed_json"})
            return

        try:
            candidate, edited = validate_payload(payload)
        except ValueError as exc:
            REQUESTS["validation_error"] += 1
            self._write_json(422, {"error": "invalid_request", "detail": str(exc)})
            return

        REQUESTS["success"] += 1
        self._write_json(200, score_edit_similarity(candidate, edited))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        self._write_response(
            status,
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            "application/json",
        )

    def _write_response(self, status: int, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def create_server(host: str = "0.0.0.0", port: int = 8080) -> HTTPServer:
    return HTTPServer((host, port), RewardHandler)


def main() -> None:
    port = int(os.environ.get("REWARD_PORT", "8080"))
    server = create_server(port=port)
    print(f"[reward] Edit-similarity service running on :{port}.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
