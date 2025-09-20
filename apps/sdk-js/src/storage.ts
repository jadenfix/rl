export interface QueueItem {
  path: string;
  payload: Record<string, unknown>;
}

export interface StorageAdapter {
  enqueue(item: QueueItem): Promise<void> | void;
  drain(): Promise<QueueItem[]> | QueueItem[];
}

export class MemoryStorageAdapter implements StorageAdapter {
  private queue: QueueItem[] = [];

  enqueue(item: QueueItem): void {
    this.queue.push(item);
  }

  drain(): QueueItem[] {
    const copy = [...this.queue];
    this.queue = [];
    return copy;
  }
}

export class LocalStorageAdapter implements StorageAdapter {
  private readonly key: string;
  private readonly storage: Storage;

  constructor(options?: { key?: string; storage?: Storage }) {
    this.key = options?.key ?? "rlaas-offline-queue";
    const storage = options?.storage ?? (typeof window !== "undefined" ? window.localStorage : undefined);
    if (!storage) {
      throw new Error("LocalStorageAdapter requires a window.localStorage implementation");
    }
    this.storage = storage;
  }

  enqueue(item: QueueItem): void {
    const queue = this.read();
    queue.push(item);
    this.write(queue);
  }

  drain(): QueueItem[] {
    const queue = this.read();
    this.storage.removeItem(this.key);
    return queue;
  }

  private read(): QueueItem[] {
    const raw = this.storage.getItem(this.key);
    if (!raw) {
      return [];
    }
    try {
      const parsed = JSON.parse(raw) as QueueItem[];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      this.storage.removeItem(this.key);
      return [];
    }
  }

  private write(queue: QueueItem[]): void {
    this.storage.setItem(this.key, JSON.stringify(queue));
  }
}

export class BrowserStorageAdapter implements StorageAdapter {
  private readonly key: string;
  private readonly storage: chrome.storage.StorageArea;

  constructor(options?: { key?: string; storage?: chrome.storage.StorageArea }) {
    if (typeof chrome === "undefined" || !chrome.storage?.local) {
      throw new Error("BrowserStorageAdapter requires chrome.storage");
    }

    this.key = options?.key ?? "rlaas-offline-queue";
    this.storage = options?.storage ?? chrome.storage.local;
  }

  async enqueue(item: QueueItem): Promise<void> {
    const queue = await this.read();
    queue.push(item);
    await this.write(queue);
  }

  async drain(): Promise<QueueItem[]> {
    const queue = await this.read();
    await this.remove();
    return queue;
  }

  private async read(): Promise<QueueItem[]> {
    const result = await this.get();
    const raw = result?.[this.key];
    if (!raw) {
      return [];
    }
    try {
      return Array.isArray(raw) ? (raw as QueueItem[]) : (JSON.parse(raw as string) as QueueItem[]);
    } catch {
      await this.remove();
      return [];
    }
  }

  private async write(queue: QueueItem[]): Promise<void> {
    const data = { [this.key]: queue };
    const maybePromise = this.storage.set(data);
    if (maybePromise && typeof (maybePromise as Promise<void>).then === "function") {
      await maybePromise;
      return;
    }
    await new Promise<void>((resolve) => this.storage.set(data, resolve));
  }

  private async get(): Promise<Record<string, unknown>> {
    const maybePromise = this.storage.get(this.key as string);
    if (maybePromise && typeof (maybePromise as Promise<Record<string, unknown>>).then === "function") {
      return (maybePromise as Promise<Record<string, unknown>>);
    }
    return new Promise((resolve) => this.storage.get(this.key, resolve));
  }

  private async remove(): Promise<void> {
    const maybePromise = this.storage.remove(this.key);
    if (maybePromise && typeof (maybePromise as Promise<void>).then === "function") {
      await maybePromise;
      return;
    }
    await new Promise<void>((resolve) => this.storage.remove(this.key, resolve));
  }
}
