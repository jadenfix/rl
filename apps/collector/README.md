# Telemetry Collector

FastAPI service that ingests interaction, output, feedback, and task result events. Validates payloads, performs lightweight PII scrubbing, and forwards batches to storage.

## Planned components
- Pydantic models aligned with `config/schemas/events/*.json`
- `/v1/interaction.create` endpoint
- `/v1/interaction.output` endpoint
- `/v1/feedback.submit` endpoint
- `/v1/task_result` endpoint
- Connection-pooled Postgres sink (hot store) with optional MinIO staging (cold store)
- OpenTelemetry instrumentation and idempotency caching
