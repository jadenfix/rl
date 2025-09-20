import type { PropsWithChildren } from "react";
import { createContext, useContext, useMemo } from "react";

import type { ClientConfig } from "../config";
import { TelemetryClient } from "../client";

const TelemetryContext = createContext<TelemetryClient | null>(null);

export interface TelemetryProviderProps extends PropsWithChildren {
  client?: TelemetryClient;
  config?: ClientConfig;
}

export function TelemetryProvider({ client, config, children }: TelemetryProviderProps) {
  const value = useMemo(() => {
    if (client) {
      return client;
    }
    if (!config) {
      throw new Error("TelemetryProvider requires either `client` or `config`.");
    }
    return new TelemetryClient(config);
  }, [client, config]);

  return <TelemetryContext.Provider value={value}>{children}</TelemetryContext.Provider>;
}

export function useTelemetryClient(): TelemetryClient {
  const ctx = useContext(TelemetryContext);
  if (!ctx) {
    throw new Error("useTelemetryClient must be used within a TelemetryProvider");
  }
  return ctx;
}

export function useTelemetryLogger() {
  const client = useTelemetryClient();
  return useMemo(
    () => ({
      logInteraction: client.logInteraction.bind(client),
      logOutput: client.logOutput.bind(client),
      submitFeedback: client.submitFeedback.bind(client),
      logTaskResult: client.logTaskResult.bind(client),
      validate: client.validate.bind(client),
      flushOffline: client.flushOffline.bind(client),
    }),
    [client],
  );
}

export type { TelemetryClient };
