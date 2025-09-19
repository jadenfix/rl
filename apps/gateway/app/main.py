from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class GatewayHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server interface)
        if self.path == "/healthz":
            self._write_json({"status": "ok", "service": "gateway"})
        elif self.path == "/metrics":
            body = "placeholder_metric 1\n"
            self._write_response(body, content_type="text/plain; version=0.0.4")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003 (shadow built-in)
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
    server = HTTPServer(("0.0.0.0", 8000), GatewayHandler)
    print("[gateway] Placeholder service running on :8000. Replace with FastAPI implementation in Phase 1/2.")
    server.serve_forever()


if __name__ == "__main__":
    main()
