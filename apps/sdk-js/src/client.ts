import { resolveConfig, type ClientConfig, type ResolvedConfig } from "./config";
import type {
  FeedbackSubmitEvent,
  InteractionCreateEvent,
  InteractionOutputEvent,
  TaskResultEvent,
  ValidateResponse,
} from "./types";
import { MemoryStorageAdapter, type QueueItem, type StorageAdapter } from "./storage";

interface PostOptions {
  bufferOnFailure?: boolean;
  expectJson?: boolean;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export class TelemetryClient {
  private readonly config: ResolvedConfig;
  private readonly storage?: StorageAdapter;

  constructor(config: ClientConfig) {
    this.config = resolveConfig(config);
    this.storage = this.config.storage ?? new MemoryStorageAdapter();
  }

  private headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.config.apiKey}`,
      "Content-Type": "application/json",
      "User-Agent": this.config.userAgent,
      ...this.config.headers,
    };
  }

  private async post<T = unknown>(path: string, payload: Record<string, unknown>, options?: PostOptions): Promise<T | undefined> {
    const { bufferOnFailure = true, expectJson = false } = options ?? {};
    const url = `${this.config.baseUrl}${path}`;
    const body = JSON.stringify(payload);

    let attempt = 0;
    while (attempt <= this.config.maxRetries) {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), this.config.timeoutMs);
        const response = await this.config.fetchFn(url, {
          method: "POST",
          headers: this.headers(),
          body,
          signal: controller.signal,
        });
        clearTimeout(timeout);

        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }

        return expectJson ? ((await response.json()) as T) : undefined;
      } catch (error) {
        attempt += 1;
        if (attempt > this.config.maxRetries) {
          if (bufferOnFailure && this.storage) {
            await Promise.resolve(this.storage.enqueue({ path, payload } satisfies QueueItem));
          }
          throw error;
        }
        const delay = this.config.backoffMs * Math.pow(2, attempt - 1);
        await sleep(delay);
      }
    }
    return undefined;
  }

  async logInteraction(event: InteractionCreateEvent): Promise<void> {
    await this.post("/v1/interaction.create", event);
  }

  async logOutput(event: InteractionOutputEvent): Promise<void> {
    await this.post("/v1/interaction.output", event);
  }

  async submitFeedback(event: FeedbackSubmitEvent): Promise<void> {
    await this.post("/v1/feedback.submit", event);
  }

  async logTaskResult(event: TaskResultEvent): Promise<void> {
    await this.post("/v1/task_result", event);
  }

  async validate(payload: Record<string, unknown>): Promise<ValidateResponse> {
    const result = await this.post<ValidateResponse>("/v1/validate", payload, { expectJson: true, bufferOnFailure: false });
    if (!result) {
      throw new Error("Expected JSON response from validate endpoint");
    }
    return result;
  }

  async flushOffline(): Promise<number> {
    if (!this.storage) {
      return 0;
    }
    const queued = await Promise.resolve(this.storage.drain());
    if (queued.length === 0) {
      return 0;
    }

    let successCount = 0;
    for (let index = 0; index < queued.length; index += 1) {
      const item = queued[index];
      try {
        await this.post(item.path, item.payload, { bufferOnFailure: false });
        successCount += 1;
      } catch (error) {
        // Re-enqueue failed item and remaining queue to preserve order.
        await Promise.resolve(this.storage.enqueue(item));
        for (let j = index + 1; j < queued.length; j += 1) {
          await Promise.resolve(this.storage.enqueue(queued[j]));
        }
        throw error;
      }
    }
    return successCount;
  }
}

export default TelemetryClient;
