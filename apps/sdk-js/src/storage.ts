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
