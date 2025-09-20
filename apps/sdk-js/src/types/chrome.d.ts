declare namespace chrome {
  namespace storage {
    interface StorageArea {
      get(keys?: string | string[] | Record<string, unknown>): Promise<Record<string, unknown>> | void;
      get(keys: string | string[] | Record<string, unknown>, callback: (items: Record<string, unknown>) => void): void;
      set(items: Record<string, unknown>): Promise<void> | void;
      set(items: Record<string, unknown>, callback: () => void): void;
      remove(keys: string | string[]): Promise<void> | void;
      remove(keys: string | string[], callback: () => void): void;
    }

    const local: StorageArea;
  }
}
