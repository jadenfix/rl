# SDK Workplan (Phase 1)

## Python SDK
- [x] Implement sync HTTP client with retry/backoff using `httpx` (`apps/sdk-python/src/rl_sdk/client.py`).
- [x] Provide file-backed offline buffer with manual flush and tests (`apps/sdk-python/src/rl_sdk/buffer.py`).
- [x] Ship unit tests covering retry logic, offline queue replay, and schema validation entry points (`apps/sdk-python/tests/test_client.py`).
- [ ] Promote async helpers via `httpx.AsyncClient` and `anyio` wrappers.
- [ ] Bundle middleware helpers (FastAPI/Starlette) to record inbound/outbound payloads automatically.
- [ ] Expose CLI commands for payload validation (`validate`, `drain-queue`).

## TypeScript SDK
- [x] Build core client with fetch + AbortController, including retry policies and exponential backoff (`apps/sdk-js/src/client.ts`).
- [x] Implement pluggable storage adapters (in-memory + localStorage) for offline buffering (`apps/sdk-js/src/storage.ts`).
- [x] Add Vitest coverage for transport retries, buffering, and validation responses (`apps/sdk-js/test/client.test.ts`).
- [ ] Deliver React hooks (`useTelemetry`, `useFeedback`) and vanilla helpers for browser extensions.
- [ ] Include Node.js adapter with keep-alive agent and optional proxy configuration.
- [ ] Generate TypeScript types from shared JSON Schemas (via `typescript-json-schema`).

## Shared tasks
- [x] Establish OpenAPI spec export from collector to distribute typed clients (`scripts/generate_openapi.py`, `docs/openapi/collector.json`).
- [ ] Define idempotency strategy (header + payload hash) and integrate with SDK defaults.
- [ ] Document integration examples (support draft app) referencing smoke-test checklist.
