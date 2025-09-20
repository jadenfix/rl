import { afterEach, describe, expect, it, vi } from "vitest";

import { BrowserStorageAdapter, MemoryStorageAdapter, LocalStorageAdapter } from "../src/storage";

describe("Storage adapters", () => {
  it("memory adapter drains in order", () => {
    const adapter = new MemoryStorageAdapter();
    adapter.enqueue({ path: "/", payload: { a: 1 } });
    adapter.enqueue({ path: "/b", payload: { b: 2 } });
    const drained = adapter.drain();
    expect(drained).toHaveLength(2);
    expect(adapter.drain()).toHaveLength(0);
  });

  it("localStorage adapter persists to storage", () => {
    const mockStorage = {
      data: new Map<string, string>(),
      getItem: vi.fn(function (this: any, key: string) { return this.data.get(key) ?? null; }),
      setItem: vi.fn(function (this: any, key: string, value: string) { this.data.set(key, value); }),
      removeItem: vi.fn(function (this: any, key: string) { this.data.delete(key); }),
    } as unknown as Storage;

    const adapter = new LocalStorageAdapter({ storage: mockStorage });
    adapter.enqueue({ path: "/", payload: { a: 1 } });
    expect(mockStorage.setItem).toHaveBeenCalled();
    const drained = adapter.drain();
    expect(drained).toHaveLength(1);
  });
});

describe("BrowserStorageAdapter", () => {
  const originalChrome = globalThis.chrome;

  afterEach(() => {
    if (originalChrome) {
      globalThis.chrome = originalChrome;
    } else {
      // @ts-ignore
      delete globalThis.chrome;
    }
  });

  function setupChrome() {
    const store: Record<string, unknown> = {};
    const storageArea = {
      get: vi.fn((keys: string | Record<string, unknown>) => {
        if (typeof keys === "string") {
          return Promise.resolve({ [keys]: store[keys] });
        }
        return Promise.resolve(store);
      }),
      set: vi.fn(async (items: Record<string, unknown>) => {
        Object.assign(store, items);
      }),
      remove: vi.fn(async (keys: string) => {
        delete store[keys];
      }),
    };
    // @ts-ignore
    globalThis.chrome = { storage: { local: storageArea } };
    return storageArea;
  }

  it("throws if chrome storage unavailable", () => {
    // @ts-ignore
    delete globalThis.chrome;
    expect(() => new BrowserStorageAdapter()).toThrow();
  });

  it("stores and drains queue using chrome.storage", async () => {
    const storageArea = setupChrome();
    const adapter = new BrowserStorageAdapter();
    await adapter.enqueue({ path: "/", payload: { value: 1 } });
    expect(storageArea.set).toHaveBeenCalled();
    const drained = await adapter.drain();
    expect(drained).toHaveLength(1);
    expect(storageArea.remove).toHaveBeenCalled();
  });
});
