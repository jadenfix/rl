import { describe, expect, it, vi } from "vitest";

import { TelemetryClient } from "../src/client";
import type { ClientConfig } from "../src/config";
import type { QueueItem, StorageAdapter } from "../src/storage";

class TestStorage implements StorageAdapter {
  items: QueueItem[] = [];

  enqueue(item: QueueItem): void {
    this.items.push(item);
  }

  drain(): QueueItem[] {
    const copy = [...this.items];
    this.items = [];
    return copy;
  }
}

function createConfig(overrides: Partial<ClientConfig> = {}): ClientConfig {
  return {
    baseUrl: "https://collector.example.com",
    apiKey: "test-key",
    maxRetries: 0,
    backoffMs: 0,
    timeoutMs: 1000,
    fetchFn: overrides.fetchFn,
    storage: overrides.storage,
    headers: overrides.headers,
  };
}

const sampleInteraction = {
  tenant_id: "acme",
  user_id: "user-123",
  skill: "support",
  input: { text: "Hello" },
  version: { policy_id: "policy@v1" },
  timings: { ms_total: 10 },
  costs: { tokens_in: 1, tokens_out: 2 },
};

describe("TelemetryClient", () => {
it("sends interaction events with auth headers", async () => {
  const fetchMock = vi.fn(async () => new Response(null, { status: 202 }));
  const client = new TelemetryClient({ ...createConfig({ fetchFn: fetchMock }) });
  await client.logInteraction(sampleInteraction);

  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("https://collector.example.com/v1/interaction.create");
  expect(init?.method).toBe("POST");
  expect(init?.headers?.Authorization).toBe("Bearer test-key");
  expect(init?.headers?.["Content-Type"]).toBe("application/json");
  expect(init?.headers?.["Idempotency-Key"]).toBeTypeOf("string");
  const body = JSON.parse(init?.body as string);
  expect(body.idempotency_key).toBe(init?.headers?.["Idempotency-Key"]);
});

  it("buffers failed requests after retries", async () => {
    const storage = new TestStorage();
    const fetchMock = vi.fn(async () => new Response(null, { status: 503 }));
  const client = new TelemetryClient({
    ...createConfig({ fetchFn: fetchMock }),
    maxRetries: 1,
    backoffMs: 0,
    storage,
  });

  await expect(client.logTaskResult({ tenant_id: "acme", interaction_id: "1", label: {} })).rejects.toThrow();
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(storage.items.length).toBe(1);
  expect(storage.items[0].path).toBe("/v1/task_result");
  expect(storage.items[0].payload.idempotency_key).toBeTypeOf("string");
});

  it("flushes buffered events", async () => {
    const storage = new TestStorage();
    storage.enqueue({ path: "/v1/interaction.output", payload: { tenant_id: "acme", interaction_id: "1", output: {}, timings: {}, costs: {}, version: {} } });

  const fetchMock = vi.fn(async () => new Response(null, { status: 202 }));
  const client = new TelemetryClient({
    ...createConfig({ fetchFn: fetchMock }),
    storage,
  });

  const flushed = await client.flushOffline();
  expect(flushed).toBe(1);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(storage.items.length).toBe(0);
  const [, init] = fetchMock.mock.calls[0];
  const body = JSON.parse(init?.body as string);
  expect(init?.headers?.["Idempotency-Key"]).toBe(body.idempotency_key);
});

  it("returns validate response when payload is accepted", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ event_type: "InteractionCreate", valid: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  const client = new TelemetryClient({
    ...createConfig({ fetchFn: fetchMock }),
  });

  const result = await client.validate({ tenant_id: "acme" });
  expect(result).toEqual({ event_type: "InteractionCreate", valid: true });
});

it("allows disabling auto idempotency", async () => {
  const fetchMock = vi.fn(async () => new Response(null, { status: 202 }));
  const client = new TelemetryClient({
    ...createConfig({ fetchFn: fetchMock }),
    autoIdempotency: false,
  });

  await client.submitFeedback({ tenant_id: "acme", interaction_id: "42" });
  const [, init] = fetchMock.mock.calls[0];
  expect(init?.headers?.["Idempotency-Key"]).toBeUndefined();
  const body = JSON.parse(init?.body as string);
  expect(body.idempotency_key).toBeUndefined();
});
});
