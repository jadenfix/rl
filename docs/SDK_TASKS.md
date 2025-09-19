# SDK Workplan (Phase 1)

## Python SDK
1. Implement async HTTP client with retry/backoff using `httpx`.
2. Provide sync convenience wrappers that delegate to async core via `anyio`.
3. Add local queue (SQLite or file-based) for offline buffering with background flush.
4. Bundle middleware helpers (FastAPI/Starlette) to record inbound/outbound payloads automatically.
5. Expose CLI commands for validating payloads (`validate`, `drain-queue`).
6. Ship unit tests covering retry logic, offline queue replay, and schema conformance (using `config/schemas/events`).

## TypeScript SDK
1. Build core client with fetch + AbortController, including retry policies and exponential backoff.
2. Implement pluggable storage adapters (in-memory, IndexedDB) for offline buffering.
3. Deliver React hooks (`useTelemetry`, `useFeedback`) and vanilla helpers for browser extensions.
4. Include Node.js adapter with keep-alive agent and optional proxy configuration.
5. Generate TypeScript types from shared JSON Schemas (via `typescript-json-schema`).
6. Add Jest/Vitest coverage for transport, queuing, and schema validation.

## Shared tasks
- Establish OpenAPI spec export from collector to distribute typed clients.
- Define idempotency strategy (header + payload hash) and integrate with SDK defaults.
- Document integration examples (support draft app) referencing smoke-test checklist.
