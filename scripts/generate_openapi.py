"""Generate OpenAPI schema using existing JSON event schemas."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "config" / "schemas" / "events"
OUTPUT = ROOT / "docs" / "openapi" / "collector.json"

SCHEMA_FILES = {
    "InteractionCreate": "interaction_create.json",
    "InteractionOutput": "interaction_output.json",
    "FeedbackSubmit": "feedback_submit.json",
    "TaskResult": "task_result.json",
}


def load_schemas() -> dict[str, dict]:
    data: dict[str, dict] = {}
    for name, filename in SCHEMA_FILES.items():
        with (SCHEMA_DIR / filename).open("r", encoding="utf-8") as fh:
            data[name] = json.load(fh)
    return data


def build_openapi(schemas: dict[str, dict]) -> dict:
    components = {f"{name}Event": schema for name, schema in schemas.items()}

    idempotency_parameter = {
        "name": "Idempotency-Key",
        "in": "header",
        "required": False,
        "description": "Client-provided key that guarantees at-most-once ingestion per tenant/event type.",
        "schema": {"type": "string"},
    }

    def request_body(ref: str) -> dict:
        return {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{ref}"}
                }
            },
        }

    accepted_response = {
        "description": "Event accepted for persistence",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "accepted"}
                    },
                    "required": ["status"],
                }
            }
        },
    }

    unprocessable_response = {
        "description": "Payload failed validation",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "detail": {
                            "type": "string",
                            "example": "Payload does not match any collector schema",
                        }
                    },
                }
            }
        },
    }

    paths = {
        "/healthz": {
            "get": {
                "summary": "Health check",
                "responses": {
                    "200": {
                        "description": "Service healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "ok"},
                                        "service": {
                                            "type": "string",
                                            "example": "collector",
                                        },
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/v1/interaction.create": {
            "post": {
                "summary": "Ingest interaction request event",
                "security": [{"ApiKeyAuth": []}],
                "parameters": [idempotency_parameter],
                "requestBody": request_body("InteractionCreateEvent"),
                "responses": {"202": accepted_response},
            }
        },
        "/v1/interaction.output": {
            "post": {
                "summary": "Ingest model output event",
                "security": [{"ApiKeyAuth": []}],
                "parameters": [idempotency_parameter],
                "requestBody": request_body("InteractionOutputEvent"),
                "responses": {"202": accepted_response},
            }
        },
        "/v1/feedback.submit": {
            "post": {
                "summary": "Ingest user feedback",
                "security": [{"ApiKeyAuth": []}],
                "parameters": [idempotency_parameter],
                "requestBody": request_body("FeedbackSubmitEvent"),
                "responses": {"202": accepted_response},
            }
        },
        "/v1/task_result": {
            "post": {
                "summary": "Ingest downstream task result",
                "security": [{"ApiKeyAuth": []}],
                "parameters": [idempotency_parameter],
                "requestBody": request_body("TaskResultEvent"),
                "responses": {"202": accepted_response},
            }
        },
        "/v1/validate": {
            "post": {
                "summary": "Validate payload against supported schemas",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "oneOf": [
                                    {"$ref": f"#/components/schemas/{ref}"}
                                    for ref in components.keys()
                                ],
                                "description": "Payload to validate",
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Payload valid",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event_type": {"type": "string"},
                                        "valid": {"type": "boolean"},
                                    },
                                    "required": ["event_type", "valid"],
                                }
                            }
                        },
                    },
                    "400": unprocessable_response,
                },
            }
        },
    }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "RLaaS Telemetry Collector",
            "version": "1.0.0",
            "description": "Event ingestion API for RLaaS telemetry.",
        },
        "servers": [
            {"url": "https://collector.example.com"},
            {"url": "http://localhost:8100"},
        ],
        "paths": paths,
        "components": {
            "schemas": components,
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization",
                    "description": "Use bearer API key: `Authorization: Bearer <token>`",
                }
            },
        },
    }


def main() -> None:
    schemas = load_schemas()
    openapi_doc = build_openapi(schemas)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(openapi_doc, indent=2), encoding="utf-8")
    print(f"Wrote OpenAPI schema to {OUTPUT}")


if __name__ == "__main__":
    main()
