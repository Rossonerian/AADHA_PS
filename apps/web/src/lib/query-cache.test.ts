import assert from "node:assert/strict";
import test from "node:test";
import { createQueryCache } from "./query-cache.ts";

test("fresh cache hit skips redundant fetcher calls", async () => {
  let t = 1_000;
  let calls = 0;
  const cache = createQueryCache(() => t);

  const first = await cache.fetch(
    "plan",
    async () => {
      calls += 1;
      return { level: 2, items: calls };
    },
    { ttlMs: 60_000 },
  );

  t += 30_000;
  const second = await cache.fetch(
    "plan",
    async () => {
      calls += 1;
      return { level: 2, items: calls };
    },
    { ttlMs: 60_000 },
  );

  assert.equal(calls, 1);
  assert.deepEqual(first, { level: 2, items: 1 });
  assert.deepEqual(second, first);
  assert.deepEqual(cache.peek("plan"), first);
  assert.deepEqual(cache.get("plan"), { value: first, isFresh: true });
});

test("concurrent fetch() calls for the same key share one in-flight promise", async () => {
  let calls = 0;
  let resolveFetch!: (value: string) => void;
  const cache = createQueryCache(() => 1_000);

  const fetcher = () => {
    calls += 1;
    return new Promise<string>((resolve) => {
      resolveFetch = resolve;
    });
  };

  const p1 = cache.fetch("lesson:l1", fetcher, { ttlMs: 300_000 });
  const p2 = cache.fetch("lesson:l1", fetcher, { ttlMs: 300_000 });

  assert.equal(calls, 1);
  assert.equal(p1, p2);

  resolveFetch("lesson-payload");
  const [r1, r2] = await Promise.all([p1, p2]);
  assert.equal(r1, "lesson-payload");
  assert.equal(r2, "lesson-payload");
  assert.equal(cache.peek("lesson:l1"), "lesson-payload");
});

test("rejected fetch cleans up in-flight state so a subsequent fetch retries", async () => {
  let calls = 0;
  const cache = createQueryCache(() => 1_000);

  await assert.rejects(
    cache.fetch(
      "dashboard",
      async () => {
        calls += 1;
        throw new Error("network down");
      },
      { ttlMs: 45_000 },
    ),
    /network down/,
  );

  assert.equal(cache.peek("dashboard"), null);

  const recovered = await cache.fetch(
    "dashboard",
    async () => {
      calls += 1;
      return { ok: true };
    },
    { ttlMs: 45_000 },
  );

  assert.equal(calls, 2);
  assert.deepEqual(recovered, { ok: true });
});

test("expired TTL or { force: true } re-fetches fresh data", async () => {
  let t = 10_000;
  let calls = 0;
  const cache = createQueryCache(() => t);

  const fetcher = async () => {
    calls += 1;
    return `version-${calls}`;
  };

  const initial = await cache.fetch("explain:INFY:2017", fetcher, { ttlMs: 5_000 });
  assert.equal(initial, "version-1");

  const forced = await cache.fetch("explain:INFY:2017", fetcher, {
    ttlMs: 5_000,
    force: true,
  });
  assert.equal(forced, "version-2");
  assert.equal(calls, 2);

  t += 5_000;
  assert.equal(cache.peek("explain:INFY:2017"), "version-2");
  assert.deepEqual(cache.get("explain:INFY:2017"), { value: "version-2", isFresh: false });

  const afterExpiry = await cache.fetch("explain:INFY:2017", fetcher, { ttlMs: 5_000 });
  assert.equal(afterExpiry, "version-3");
  assert.equal(calls, 3);
});

test("invalidate(prefix) evicts only matching keys and clear() evicts all keys", async () => {
  const cache = createQueryCache(() => 1_000);

  cache.set("plan", { progress: 40 }, 60_000);
  cache.set("lesson:1", { id: "1" }, 60_000);
  cache.set("lesson:2", { id: "2" }, 60_000);
  cache.set("dashboard", { level: 2 }, 60_000);

  cache.invalidate("lesson:");

  assert.equal(cache.peek("lesson:1"), null);
  assert.equal(cache.peek("lesson:2"), null);
  assert.deepEqual(cache.peek("plan"), { progress: 40 });
  assert.deepEqual(cache.peek("dashboard"), { level: 2 });

  cache.clear();

  assert.equal(cache.peek("plan"), null);
  assert.equal(cache.peek("dashboard"), null);
});

test("invalidate() during an in-flight fetch prevents stale writeback", async () => {
  let resolveStale!: (value: string) => void;
  const cache = createQueryCache(() => 1_000);

  const stalePromise = cache.fetch(
    "plan",
    () =>
      new Promise<string>((resolve) => {
        resolveStale = resolve;
      }),
    { ttlMs: 60_000 },
  );

  cache.invalidate("plan");
  resolveStale("stale-plan");
  assert.equal(await stalePromise, "stale-plan");
  assert.equal(cache.peek("plan"), null);
});
