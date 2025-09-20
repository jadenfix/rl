# TypeScript SDK

Browser and Node-friendly client for emitting telemetry into the RLaaS collector.

## What works today
- Fetch-based `TelemetryClient` with retries, exponential backoff, and request timeouts (`src/client.ts`).
- Offline buffering via pluggable storage adapters (`MemoryStorageAdapter`, `LocalStorageAdapter`) so events survive transient outages (`src/storage.ts`).
- Vitest coverage for retry logic, buffering, and `/v1/validate` responses (`test/client.test.ts`).
- React helpers (`TelemetryProvider`, `useTelemetryClient`, `useTelemetryLogger`) for drop-in instrumentation inside web apps (`src/react`).

## Roadmap
- React hooks + middleware helpers for browser extensions and shared UI components.
  - Custom hook for passive flush / online detection.
- Node-specific adapter with keep-alive agent, proxy controls, and streaming support.
- Generated TypeScript types from shared JSON Schemas.
- End-to-end examples (Gmail, Zendesk, Salesforce) mirroring the integration playbook in `docs/`.
