import { beforeEach, describe, expect, it, vi } from "vitest";

const agentMock = vi.fn().mockImplementation(() => ({ type: "agent" }));
const proxyAgentMock = vi.fn().mockImplementation(() => ({ type: "proxy" }));
const fetchMock = vi.fn(async (_input, init) => ({ ok: true, status: 202, init }));

vi.mock("undici", () => ({
  Agent: agentMock,
  ProxyAgent: proxyAgentMock,
  fetch: fetchMock,
}));

import { createNodeFetch, createNodeTelemetryClient } from "../src/node";
import { TelemetryClient } from "../src/client";

beforeEach(() => {
  agentMock.mockClear();
  proxyAgentMock.mockClear();
  fetchMock.mockClear();
});

describe("Node adapter", () => {
  it("creates dispatcher with keep-alive agent", async () => {
    const fn = createNodeFetch({ keepAliveTimeout: 5000, keepAliveMaxTimeout: 15000, connections: 20 });
    await fn("https://example.com", { method: "POST" });

    expect(agentMock).toHaveBeenCalledWith({ keepAliveTimeout: 5000, keepAliveMaxTimeout: 15000, connections: 20 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const args = fetchMock.mock.calls[0][1];
    expect(args?.dispatcher).toBeDefined();
  });

  it("uses proxy agent when proxy URL provided", async () => {
    const fn = createNodeFetch({ proxyUrl: "http://proxy.local:8888", connections: 50 });
    await fn("https://example.com");
    expect(proxyAgentMock).toHaveBeenCalledWith("http://proxy.local:8888", { connections: 50 });
  });

  it("constructs telemetry client with node fetch", () => {
    const client = createNodeTelemetryClient({ baseUrl: "https://collector", apiKey: "test", proxyUrl: "http://proxy" });
    expect(client).toBeInstanceOf(TelemetryClient);
    expect(proxyAgentMock).toHaveBeenCalled();
  });
});
