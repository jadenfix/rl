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
