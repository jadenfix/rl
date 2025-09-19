import type { StorageAdapter } from "./storage";

export interface ClientConfig {
  baseUrl: string;
  apiKey: string;
  maxRetries?: number;
  backoffMs?: number;
  timeoutMs?: number;
  headers?: Record<string, string>;
  userAgent?: string;
  storage?: StorageAdapter | null;
  fetchFn?: typeof fetch;
}

export interface ResolvedConfig {
  baseUrl: string;
  apiKey: string;
  maxRetries: number;
  backoffMs: number;
  timeoutMs: number;
  headers: Record<string, string>;
  userAgent: string;
  storage?: StorageAdapter;
  fetchFn: typeof fetch;
}

export function resolveConfig(config: ClientConfig): ResolvedConfig {
  const fetchFn = config.fetchFn ?? (typeof fetch !== "undefined" ? fetch.bind(globalThis) : undefined);
  if (!fetchFn) {
    throw new Error("No fetch implementation found. Provide config.fetchFn in non-browser/non-Node environments.");
  }

  return {
    baseUrl: config.baseUrl.replace(/\/$/, ""),
    apiKey: config.apiKey,
    maxRetries: config.maxRetries ?? 3,
    backoffMs: config.backoffMs ?? 500,
    timeoutMs: config.timeoutMs ?? 5000,
    headers: config.headers ?? {},
    userAgent: config.userAgent ?? "rlaas-sdk-js/0.1.0",
    storage: config.storage ?? undefined,
    fetchFn,
  };
}
