# RLaaS Monorepo

This repository hosts the services, SDKs, and infrastructure needed to operate the RLaaS platform described in `plan.md` and sequenced via `roadmap.md`.

## Structure
- `apps/gateway` — FastAPI inference gateway with policy routing and telemetry hooks.
- `apps/collector` — FastAPI telemetry ingestion service for interactions, feedback, and task results.
- `apps/reward` — Reward calculation workers and APIs for preference generation.
- `apps/trainer` — Offline training pipelines for LoRA adapters and reward models.
- `apps/dashboard` — Next.js admin console for operators and auditors.
- `apps/sdk-python` — Python instrumentation SDK for backend workflows.
- `apps/sdk-js` — TypeScript instrumentation SDK for web and extension environments.
- `config/` — Environment templates, migrations, and shared schemas.
- `scripts/` — Operational scripts (seeding, maintenance, developer tooling).
- `docs/` — Architecture notes and integration guides.

## Getting started
1. Install Docker and Docker Compose v2.
2. Copy `config/.env.example` to `.env` and update secrets (use local Docker Postgres values or a managed service such as Neon).
3. Run `psql "$DATABASE_URL" -f config/db/init.sql -f config/db/seed.sql` once to create tables and seed the sample tenant/policy.
4. Run `make up` to launch the stack; services will be available once migrations complete.
5. Hit each service `http://localhost:{8000,8080,8090,8100}/healthz` to confirm the stack is healthy, then verify seed data in Postgres.
6. Run `make openapi` to regenerate the collector OpenAPI schema (`docs/openapi/collector.json`) and share it with SDK consumers.
7. (Optional) Ensure MinIO staging works by sending a sample event and running `make compact` to roll JSONL blobs into a Parquet artifact under `events/parquet/dt=<date>/`.

Refer to `progress.md` for the latest implementation status and upcoming checkpoints.

## Telemetry instrumentation (Phase 1)
- Collector persists events to Postgres and stages JSONL copies in MinIO for downstream compaction (`apps/collector/app/storage.py`).
- Daily compaction to Parquet is handled by `apps/collector/app/compaction.py`; invoke via `make compact` or `python3 -m apps.collector.app.compaction --date YYYY-MM-DD`.
- OpenAPI schema generation pulls from the shared JSON Schemas via `scripts/generate_openapi.py` (also available through `make openapi`).
- Python SDK (`apps/sdk-python`) ships a retrying telemetry client with file-backed offline buffering and pytest coverage for failure modes.
- PII scrubbing hooks redact common patterns (email, phone, payment, SSN) with tenant allow-list overrides (`apps/collector/app/pii.py`).
