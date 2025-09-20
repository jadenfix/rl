import { renderHook, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TelemetryClient } from "../src/client";
import type { ClientConfig } from "../src/config";
import { TelemetryProvider, useTelemetryClient, useTelemetryLogger } from "../src/react";

const baseConfig: ClientConfig = {
  baseUrl: "https://collector.example.com",
  apiKey: "test-key",
  fetchFn: vi.fn(async () => new Response(null, { status: 202 })),
};

describe("TelemetryProvider", () => {
  beforeEach(() => {
    (baseConfig.fetchFn as ReturnType<typeof vi.fn>).mockClear();
  });

  it("exposes provided client instance", () => {
    const client = new TelemetryClient({ ...baseConfig });
    const { result } = renderHook(() => useTelemetryClient(), {
      wrapper: ({ children }) => <TelemetryProvider client={client}>{children}</TelemetryProvider>,
    });
    expect(result.current).toBe(client);
  });

  it("creates client from config and logs interactions", async () => {
    const { result } = renderHook(() => useTelemetryLogger(), {
      wrapper: ({ children }) => <TelemetryProvider config={baseConfig}>{children}</TelemetryProvider>,
    });

    await act(async () => {
      await result.current.logInteraction({
        tenant_id: "acme",
        user_id: "user",
        skill: "support",
        input: { text: "hello" },
        version: { policy_id: "policy@v1" },
        timings: { ms_total: 1 },
        costs: { tokens_in: 1, tokens_out: 1 },
      });
    });

    expect((baseConfig.fetchFn as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(1);
  });

  it("throws when used outside provider", () => {
    expect(() => renderHook(() => useTelemetryClient())).toThrowError(/TelemetryProvider/);
  });
});
