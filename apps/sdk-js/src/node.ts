import { Agent, ProxyAgent, fetch as undiciFetch, type Dispatcher } from "undici";

import type { ClientConfig } from "./config";
import { TelemetryClient } from "./client";

export interface NodeAdapterOptions {
  proxyUrl?: string;
  keepAliveTimeout?: number;
  keepAliveMaxTimeout?: number;
  connections?: number;
}

export interface NodeClientOptions extends ClientConfig, NodeAdapterOptions {}

function createDispatcher(options: NodeAdapterOptions = {}): Dispatcher {
  const {
    proxyUrl,
    keepAliveTimeout = 10_000,
    keepAliveMaxTimeout = 30_000,
    connections = 128,
  } = options;

  if (proxyUrl) {
    return new ProxyAgent(proxyUrl, { connections });
  }

  return new Agent({
    keepAliveTimeout,
    keepAliveMaxTimeout,
    connections,
  });
}

export function createNodeFetch(options: NodeAdapterOptions = {}) {
  const dispatcher = createDispatcher(options);
  return async function nodeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    return undiciFetch(input, { ...init, dispatcher });
  };
}

export function createNodeTelemetryClient(options: NodeClientOptions): TelemetryClient {
  const { proxyUrl, keepAliveTimeout, keepAliveMaxTimeout, connections, fetchFn, ...config } = options;
  const dispatcherOptions: NodeAdapterOptions = { proxyUrl, keepAliveTimeout, keepAliveMaxTimeout, connections };
  const nodeFetch = fetchFn ?? createNodeFetch(dispatcherOptions);
  return new TelemetryClient({ ...config, fetchFn: nodeFetch });
}

export { TelemetryClient };
