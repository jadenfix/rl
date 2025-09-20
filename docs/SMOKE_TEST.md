# Phase 0 Local Smoke Test

Use these steps to validate a fresh developer environment before beginning Phase 1 telemetry work.

## 1. Environment preparation
1. Copy `config/.env.example` to `.env` and adjust values if needed.
2. Ensure Docker Desktop (or compatible engine) is running.
3. Run `pre-commit install` to activate repo hooks.

## 2. Launch the stack
```bash
make up
```
This builds the placeholder services and brings up Postgres, MinIO, Qdrant, Prometheus, and Grafana. The first run seeds the database via `config/db/init.sql` and `config/db/seed.sql`.

## 3. Verify service health
- Collector: `curl -s http://localhost:8100/healthz`
- Gateway: `curl -s http://localhost:8000/healthz`
- Reward service: `curl -s http://localhost:8080/healthz`
- Trainer service: `curl -s http://localhost:8090/healthz`
- Prometheus UI: `http://localhost:${PROMETHEUS_PORT}` (default `9091`)
- Grafana UI: `http://localhost:${GRAFANA_PORT}` (default `3000`)

Each health check should return `{"status": "ok", ...}` and `/metrics` endpoints should serve placeholder counters.

## 4. Inspect seeded data
```bash
make ps
# get Postgres container name (defaults to rlaas-postgres)
make logs postgres
# or use psql directly
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB" \
  -c "SELECT tenant_slug, display_name FROM tenants;" \
  -c "SELECT api_token FROM api_keys;" \
  -c "SELECT policy_id, status FROM policies;"
```
Expected results:
- One tenant `acme-support`
- API key `acme-support-key`
- Policy `support-draft-v0` with status `shadow`

## 5. Clean up
```bash
make down
```
Volumes are preserved between runs; remove them if a fresh seed is needed.

## 6. (Optional) Smoke-test event ingestion
Send a sample payload:

```bash
curl -X POST http://localhost:8100/v1/interaction.create \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "<tenant-uuid>",
    "user_id": "user-123",
    "skill": "support_draft_email",
    "input": {"text": "Hello world"},
    "context": {},
    "version": {"policy_id": "support-draft-v0", "base_model": "meta-llama/Meta-Llama-3.1-8B-Instruct"},
    "timings": {"ms_total": 123},
    "costs": {"tokens_in": 10, "tokens_out": 20}
  }'
```

Retrieve `<tenant-uuid>` via:

```bash
psql "$DATABASE_URL" -c "SELECT id FROM tenants WHERE tenant_slug = 'acme-support';"
```

Then verify the event landed:

```bash
psql "$DATABASE_URL" -c "SELECT event_type, occurred_at FROM events ORDER BY occurred_at DESC LIMIT 5;"
```

## 7. Phase 1 telemetry checklist

1. **PII scrubbing sanity check** — Send an event with synthetic PII (`user@example.com`, `+1-555-000-1111`) and confirm the persisted JSON (`events.payload`) stores `[REDACTED]` instead.
2. **MinIO staging** — With the stack running, configure the MinIO client (`mc alias set local http://localhost:${MINIO_PORT} $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD`) and run `mc ls local/rlaas-events/events/staging` to confirm JSONL drops into `events/staging/<event_type>/dt=<date>/`.
3. **Daily compaction dry run** — Trigger `make compact` locally. The command uploads a parquet batch to `events/parquet/dt=<date>/events-<time>.parquet` in MinIO. Inspect the file via `mc cat local/rlaas-events/<path>` or download through the console.
4. **Gateway smoke** — POST to `http://localhost:8000/v1/infer` with a sample payload. With `GATEWAY_USE_STUB_BACKEND=true` you should see a stubbed response and corresponding `interaction.output` rows in the collector. Example:

```bash
curl -X POST http://localhost:8000/v1/infer \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "acme-support",
    "skill": "support_draft_email",
    "input": {"text": "Customer is asking about refunds."}
  }'
```

5. **Idempotency dedupe** — Send the same payload twice with the header `Idempotency-Key: test-key-123`. The second call should return `202` and no duplicate row should appear in `events` (check via `SELECT COUNT(*) FROM events WHERE payload->>'idempotency_key' = 'test-key-123';`).
6. **OpenAPI export** — Run `make openapi` to regenerate `docs/openapi/collector.json`. Share this artifact with SDK consumers to ensure consistent typing.

> Switching to a real inference backend? Set `INFERENCE_BASE_URL` and `INFERENCE_API_KEY` in `.env`, and flip `GATEWAY_USE_STUB_BACKEND=false` before running `make up`.
> The gateway will ping `/healthz` on the backend during startup and log the result.
> The default docker-compose ships a stub inference service at `http://localhost:9001` (see `apps/inference`).

> Upgrading an existing database? Apply the idempotency schema patch manually:
> ```sql
> ALTER TABLE events ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
> CREATE UNIQUE INDEX IF NOT EXISTS uniq_events_idempotency
>   ON events (tenant_id, event_type, idempotency_key)
>   WHERE idempotency_key IS NOT NULL;
> ```
