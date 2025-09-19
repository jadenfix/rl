from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class RewardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._write_json({"status": "ok", "service": "reward"})
        elif self.path == "/metrics":
            body = "reward_placeholder_metric 1\n"
            self._write_response(body, content_type="text/plain; version=0.0.4")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _write_json(self, payload: dict) -> None:
        self._write_response(json.dumps(payload), content_type="application/json")

    def _write_response(self, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    server = HTTPServer(("0.0.0.0", 8080), RewardHandler)
    print("[reward] Placeholder service running on :8080. Reward engines land in Phase 4.")
    server.serve_forever()


if __name__ == "__main__":
    main()
