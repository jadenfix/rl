Progress log — RLaaS implementation

2025-09-18
- 16:05 PDT — Reviewed `plan.md` and `roadmap.md` to understand pillars, phases, and MVP scope; identified need for explicit crosswalk plus immediate action list.
- 16:12 PDT — Added "Implementation alignment" section to `plan.md` (`plan.md:7`) summarizing how roadmap phases map onto plan pillars and captured the three Phase 0 critical actions.
- 16:18 PDT — Reintroduced structural divider (`plan.md:19`) to maintain readability after the new section.
- 16:22 PDT — Annotated `roadmap.md` Phase 0–2 blocks with live status notes tying them to the Plan P0 steps and clarifying which workstreams are blocked or pending (`roadmap.md:9`, `roadmap.md:23`, `roadmap.md:35`).
- 16:29 PDT — Scaffolded monorepo directories and placeholder service READMEs across gateway, reward, trainer, dashboard, and SDK apps; added repo-level docs, `.gitignore`, and pre-commit tooling (`apps/gateway/README.md`, `apps/reward/README.md`, `.pre-commit-config.yaml`).
- 16:36 PDT — Introduced docker-compose stack with placeholder Python HTTP services, Prometheus/Grafana observability, env template, and Makefile automation for `make up/down/logs/seed` (`docker-compose.yml`, `config/.env.example`, `Makefile`).
- 16:42 PDT — Defined Postgres schema + seed routines for tenants, API keys, policies, and bootstrap events to satisfy Phase 0 gate (`config/db/init.sql`, `config/db/seed.sql`).
- 16:48 PDT — Attempted `make up`; run blocked because Docker daemon unavailable in sandbox. Documented command in `progress.md` and ensured `.env` copied locally for future runs.
- 16:55 PDT — Authored Phase 0 smoke-test procedure detailing bring-up, health checks, and seed verification for developers with Docker access (`docs/SMOKE_TEST.md`, `docs/README.md:9`).
- 17:00 PDT — Second `make up` attempt still blocked by Mac sandbox (permission denied on Docker socket); requires running outside CLI sandbox or granting socket access manually.
- 17:08 PDT — User ran `make up` locally; stack containers are up per Docker output. Pending manual health checks and seed verification (see `docs/SMOKE_TEST.md`).
- 17:15 PDT — Authored JSON Schemas for all Phase 1 events (`config/schemas/events/*.json`) to align SDK contracts with plan data model.
- 17:24 PDT — Added FastAPI-based telemetry collector with Pydantic models, validation endpoint, Docker image, and Prometheus scraping (`apps/collector/app`, `apps/collector/Dockerfile`, `docker-compose.yml:4`).
- 17:30 PDT — Outlined Python/TypeScript SDK workplan covering transport, buffering, schema typing, and shared tasks (`docs/SDK_TASKS.md`).
- 17:38 PDT — Connected to Neon Postgres instance and executed schema + seed scripts successfully (`config/db/init.sql`, `config/db/seed.sql`), enabling remote tenant bootstrap.
- 2025-09-19 12:15 PDT — Verified Neon seed data via psql (tenant `acme-support`, api key `acme-support-key`, policy `support-draft-v0` @ `shadow` status).
- 2025-09-19 12:18 PDT — User confirmed local `/healthz` checks across gateway, reward, trainer, and collector services (Phase 0 gate closed).
- 2025-09-19 12:28 PDT — Wired collector persistence through connection-pooled Postgres writes with optional MinIO staging hooks (`apps/collector/app/main.py`, `apps/collector/app/storage.py`, `apps/collector/requirements.txt`).
- 2025-09-19 12:35 PDT — Updated docs and configuration to reflect remote Postgres workflow and ingestion smoke tests (`README.md`, `docs/SMOKE_TEST.md`, `.env`).
- 2025-09-19 12:45 PDT — Initialized git repo, captured initial commit, and pushed history to `origin/main` for GitHub sharing (`git init`, `git push -u origin main`).
- 2025-09-19 12:52 PDT — Expanded `roadmap.md` Phase 1 section with sprint focus checklist covering MinIO staging, OpenAPI artifacts, SDK transport, and PII scrub tasks (`roadmap.md:35`).
- 2025-09-19 12:55 PDT — Documented Phase 2 dependency notes in `roadmap.md`, clarifying readiness of the gateway skeleton and sequencing behind telemetry stability (`roadmap.md:57`).
- 2025-09-19 13:08 PDT — Implemented MinIO staging pipeline with bucket bootstrap, JSONL uploads, and secure configuration toggles (`apps/collector/app/storage.py`, `docker-compose.yml`, `config/.env.example`).
- 2025-09-19 13:14 PDT — Added Parquet compaction CLI, Makefile target, and smoke-test instructions for daily cold storage promotion (`apps/collector/app/compaction.py`, `Makefile`, `docs/SMOKE_TEST.md`).
- 2025-09-19 13:18 PDT — Delivered regex-driven PII scrubbing with tenant allow-list overrides and unit coverage (`apps/collector/app/pii.py`, `apps/collector/tests/test_pii.py`).
- 2025-09-19 13:24 PDT — Generated OpenAPI artifacts directly from shared JSON schemas via `scripts/generate_openapi.py` (`docs/openapi/collector.json`).
- 2025-09-19 13:34 PDT — Shipped Python SDK client with retry/backoff, file-backed offline buffer, and pytest suite (`apps/sdk-python/src/rl_sdk`, `apps/sdk-python/tests/test_client.py`, `apps/sdk-python/pyproject.toml`).
- 2025-09-19 13:42 PDT — Updated top-level documentation and plan to capture Phase 1 readiness, telemetry tooling, and SDK deliverables (`README.md`, `plan.md`, `roadmap.md`, `docs/SDK_TASKS.md`).
- 2025-09-19 13:58 PDT — Scaffolded TypeScript SDK package with build/test tooling (tsconfig, vitest config, package manifest) and shared storage adapters (`apps/sdk-js/package.json`, `apps/sdk-js/src/storage.ts`).
- 2025-09-19 14:05 PDT — Implemented fetch-based telemetry client with retries, timeouts, and offline flush plus Vitest coverage for success, retry, buffering, and validate flows (`apps/sdk-js/src/client.ts`, `apps/sdk-js/test/client.test.ts`).
- 2025-09-19 14:12 PDT — Updated SDK roadmap and README docs to reflect TypeScript parity and remaining front-end tasks (`docs/SDK_TASKS.md`, `apps/sdk-js/README.md`, `README.md`, `plan.md`, `roadmap.md`).
- 2025-09-19 14:26 PDT — Added event-level idempotency (column, unique index, header plumbing) and updated collector storage to dedupe writes safely (`config/db/init.sql`, `apps/collector/app/main.py`, `apps/collector/app/storage.py`).
- 2025-09-19 14:31 PDT — Extended Python SDK to auto-generate `Idempotency-Key` headers with opt-out and expanded pytest coverage for retries/buffering under dedupe (`apps/sdk-python/src/rl_sdk/client.py`, `apps/sdk-python/tests/test_client.py`).
- 2025-09-19 14:36 PDT — Mirrored idempotency support in the TypeScript SDK with auto key generation, storage replay, and Vitest assertions (`apps/sdk-js/src/client.ts`, `apps/sdk-js/test/client.test.ts`).
- 2025-09-19 14:40 PDT — Regenerated OpenAPI docs to advertise the `Idempotency-Key` header and refreshed smoke tests/README for the schema upgrade path (`scripts/generate_openapi.py`, `docs/openapi/collector.json`, `docs/SMOKE_TEST.md`, `README.md`).
- 2025-09-19 14:48 PDT — Added React provider/hooks wrapper for the TypeScript SDK to simplify in-app telemetry wiring and covered with Vitest renderHook tests (`apps/sdk-js/src/react`, `apps/sdk-js/test/react.test.tsx`).
- 2025-09-19 14:55 PDT — Authored end-to-end support draft integration guide covering Python + React instrumentation, idempotency, and verification steps (`docs/examples/support_draft.md`, `README.md`, `docs/README.md`).

Current focus
- Document integration examples (support draft app) referencing smoke-test checklist.

Next checkpoints
- Ship documentation/examples for support draft integration path.
- Add Node adapter + extension helpers for telemetry capture.
