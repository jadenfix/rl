from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[3]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class RewardHttpE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = free_port()
        env = os.environ.copy()
        env["REWARD_PORT"] = str(cls.port)
        cls.process = subprocess.Popen(
            [sys.executable, "apps/reward/app/main.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                status, _ = cls.request("GET", "/healthz")
                if status == 200:
                    return
            except OSError:
                time.sleep(0.05)
        output = cls.process.stdout.read() if cls.process.stdout else ""
        raise RuntimeError(f"reward service did not start: {output}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.process.terminate()
        cls.process.wait(timeout=5)

    @classmethod
    def request(
        cls,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        connection = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read().decode("utf-8")
        connection.close()
        return response.status, payload

    @classmethod
    def score(cls, candidate: str, edited: str) -> tuple[int, dict]:
        body = json.dumps({"candidate": candidate, "edited": edited}).encode()
        status, payload = cls.request(
            "POST",
            "/v1/rewards/edit-similarity",
            body,
            {"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        return status, json.loads(payload)

    def test_valid_unchanged_and_rewritten_requests(self) -> None:
        status, unchanged = self.score("Ready to ship.", "Ready to ship.")
        self.assertEqual(status, 200)
        self.assertEqual(unchanged["score"], 1.0)
        self.assertEqual(unchanged["distance"], 0)

        status, rewritten = self.score("Hello customer", "Hello there")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(rewritten["score"], 0.0)
        self.assertLess(rewritten["score"], 1.0)
        self.assertGreater(rewritten["distance"], 0)

    def test_malformed_json_is_rejected(self) -> None:
        body = b'{"candidate":'
        status, payload = self.request(
            "POST",
            "/v1/rewards/edit-similarity",
            body,
            {"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(payload)["error"], "malformed_json")

    def test_oversized_body_is_rejected_without_reading_it(self) -> None:
        body = b"{}"
        status, payload = self.request(
            "POST",
            "/v1/rewards/edit-similarity",
            body,
            {"Content-Type": "application/json", "Content-Length": "65537"},
        )
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(payload)["error"], "payload_too_large")

    def test_metrics_count_outcomes(self) -> None:
        self.score("one", "two")
        malformed = b"{"
        self.request(
            "POST",
            "/v1/rewards/edit-similarity",
            malformed,
            {"Content-Type": "application/json", "Content-Length": str(len(malformed))},
        )
        self.request(
            "POST",
            "/v1/rewards/edit-similarity",
            b"{}",
            {"Content-Type": "application/json", "Content-Length": "65537"},
        )
        status, payload = self.request("GET", "/metrics")
        self.assertEqual(status, 200)
        self.assertIn('reward_requests_total{outcome="success"}', payload)
        self.assertIn('reward_requests_total{outcome="validation_error"}', payload)
        self.assertIn('reward_requests_total{outcome="payload_too_large"}', payload)


if __name__ == "__main__":
    unittest.main()
