"""Local preference reward training, scoring, checkpointing and HTTP serving."""
from __future__ import annotations

import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path

try:
    from . import model
except ImportError:  # Docker copies the app directory and invokes this script.
    import model

MAX_BODY = 2_000_000


class TrainerServer(HTTPServer):
    def __init__(self, address, checkpoint):
        self.checkpoint = Path(checkpoint)
        # Corrupt existing state fails startup, never silently becomes an untrained model.
        self.model = model.load(self.checkpoint) if self.checkpoint.exists() else None
        self.requests = Counter()
        self.training_runs = 0
        super().__init__(address, TrainerHandler)


class TrainerHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def do_GET(self):
        if self.path == "/healthz":
            self.reply(200, {"status": "ok", "service": "trainer", "model_ready": self.server.model is not None})
        elif self.path == "/v1/model":
            self.reply(200 if self.server.model else 503, self.server.model or {"error": "model_not_trained"})
        elif self.path == "/metrics":
            body = ("# TYPE trainer_training_runs_total counter\n"
                    f"trainer_training_runs_total {self.server.training_runs}\n"
                    "# TYPE trainer_model_ready gauge\n"
                    f"trainer_model_ready {int(self.server.model is not None)}\n")
            for status in sorted(self.server.requests):
                body += f'trainer_requests_total{{status="{status}"}} {self.server.requests[status]}\n'
            self.reply(200, body, "text/plain; version=0.0.4")
        else:
            self.reply(404, {"error": "not_found"})

    def do_POST(self):
        if self.path not in {"/v1/train", "/v1/score"}:
            self.reply(404, {"error": "not_found"})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.reply(415, {"error": "json_required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0:
            self.reply(411, {"error": "content_length_required"})
            return
        if length > MAX_BODY:
            self.reply(413, {"error": "payload_too_large"})
            return
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("truncated request body")
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeError):
            self.reply(400, {"error": "malformed_json"})
            return
        except TimeoutError:
            self.reply(408, {"error": "request_timeout"})
            return
        try:
            if not isinstance(payload, dict):
                raise ValueError("request must be an object")
            if self.path == "/v1/train":
                if "pairs" not in payload or set(payload) - {"pairs", "epochs", "learning_rate"}:
                    raise ValueError("expected pairs with optional epochs and learning_rate")
                trained = model.train(**payload)
                # Publish state only after its checkpoint is durably replaced.
                model.save(self.server.checkpoint, trained)
                self.server.model = trained
                self.server.training_runs += 1
                self.reply(200, trained)
            else:
                if set(payload) != {"prompt", "response"}:
                    raise ValueError("expected prompt and response")
                if self.server.model is None:
                    self.reply(503, {"error": "model_not_trained"})
                    return
                self.reply(200, model.score(self.server.model, **payload))
        except ValueError as exc:
            self.reply(422, {"error": "invalid_request", "detail": str(exc)})
        except OSError:
            self.reply(503, {"error": "checkpoint_storage_unavailable"})

    def log_message(self, *args):
        return

    def reply(self, status, payload, content_type="application/json"):
        self.server.requests[status] += 1
        body = (payload if isinstance(payload, str) else json.dumps(payload, allow_nan=False)).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default=os.getenv("TRAINER_CHECKPOINT", "data/reward-model.json"))
    sub = parser.add_subparsers(dest="command")
    train = sub.add_parser("train")
    train.add_argument("--dataset", required=True)
    train.add_argument("--epochs", type=int, default=200)
    train.add_argument("--learning-rate", type=float, default=0.5)
    score = sub.add_parser("score")
    score.add_argument("--prompt", required=True)
    score.add_argument("--response", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.getenv("TRAINER_PORT", "8090")))
    args = parser.parse_args()
    try:
        if args.command == "train":
            trained = model.train(json.loads(Path(args.dataset).read_text()), args.epochs, args.learning_rate)
            model.save(args.checkpoint, trained)
            print(json.dumps(trained, allow_nan=False))
        elif args.command == "score":
            print(json.dumps(model.score(model.load(args.checkpoint), args.prompt, args.response)))
        else:
            server = TrainerServer((getattr(args, "host", "127.0.0.1"), getattr(args, "port", 8090)), args.checkpoint)
            print(f"[trainer] Local preference reward baseline on {server.server_address}", flush=True)
            server.serve_forever()
    except (OSError, ValueError) as exc:
        parser.exit(1, f"trainer: {exc}\n")


if __name__ == "__main__":
    main()
