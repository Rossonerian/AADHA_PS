/**
 * Lightweight client-side SWR query cache with TTL tracking and in-flight deduplication.
 * Pure TypeScript (no framework or runtime dependencies) for browser and Node test runs.
 */

type CacheEntry<T> = {
  value: T;
  expiresAt: number;
};

export type QueryCacheGetResult<T> = {
  value: T;
  isFresh: boolean;
};

export type QueryCacheFetchOptions = {
  ttlMs: number;
  force?: boolean;
};

export function createQueryCache(now: () => number = () => Date.now()) {
  const entries = new Map<string, CacheEntry<unknown>>();
  const inFlight = new Map<string, Promise<unknown>>();

  function peek<T>(key: string): T | null {
    const entry = entries.get(key);
    return entry ? (entry.value as T) : null;
  }

  function get<T>(key: string): QueryCacheGetResult<T> | null {
    const entry = entries.get(key);
    if (!entry) return null;
    return {
      value: entry.value as T,
      isFresh: entry.expiresAt > now(),
    };
  }

  function set<T>(key: string, value: T, ttlMs: number): void {
    entries.set(key, {
      value,
      expiresAt: now() + ttlMs,
    });
  }

  function fetch<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: QueryCacheFetchOptions,
  ): Promise<T> {
    if (!options.force) {
      const existing = get<T>(key);
      if (existing && existing.isFresh) {
        return Promise.resolve(existing.value);
      }
      const pending = inFlight.get(key);
      if (pending) {
        return pending as Promise<T>;
      }
    }

    let run: Promise<T>;
    try {
      run = fetcher();
    } catch (error) {
      return Promise.reject(error);
    }

    const promise: Promise<T> = run
      .then((value) => {
        // Ignore stale completions if invalidated, cleared, or superseded by force=true.
        if (inFlight.get(key) === promise) {
          set(key, value, options.ttlMs);
        }
        return value;
      })
      .finally(() => {
        if (inFlight.get(key) === promise) {
          inFlight.delete(key);
        }
      });

    inFlight.set(key, promise);
    return promise;
  }

  function invalidate(prefix?: string): void {
    if (prefix === undefined) {
      entries.clear();
      inFlight.clear();
      return;
    }
    for (const key of entries.keys()) {
      if (key.startsWith(prefix)) entries.delete(key);
    }
    for (const key of inFlight.keys()) {
      if (key.startsWith(prefix)) inFlight.delete(key);
    }
  }

  function clear(): void {
    entries.clear();
    inFlight.clear();
  }

  return {
    peek,
    get,
    set,
    fetch,
    invalidate,
    clear,
  };
}

export type QueryCache = ReturnType<typeof createQueryCache>;

export const queryCache = createQueryCache();
