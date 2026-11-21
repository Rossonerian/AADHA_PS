import assert from "node:assert/strict";
import test from "node:test";
import { createTokenProvider, isJwtShaped, jwtExpiryMs } from "./auth-token.ts";

function jwt(exp: number): string {
  const enc = (o: object) => Buffer.from(JSON.stringify(o)).toString("base64url");
  return `${enc({ alg: "EdDSA" })}.${enc({ sub: "u", exp })}.sig`;
}

test("opaque session tokens are not JWT shaped", () => {
  assert.equal(isJwtShaped("abcDEF123opaqueSessionToken"), false);
  assert.equal(isJwtShaped(null), false);
  assert.equal(isJwtShaped(jwt(1)), true);
});

test("jwtExpiryMs reads exp", () => {
  assert.equal(jwtExpiryMs(jwt(1_700_000_000)), 1_700_000_000_000);
  assert.equal(jwtExpiryMs("nope"), null);
});

test("prefers /token JWT over an opaque SDK session token", async () => {
  const good = jwt(Math.floor(Date.now() / 1000) + 600);
  const p = createTokenProvider({
    fetchToken: async () => good,
    sdkToken: async () => "opaque-session-token",
  });
  assert.equal(await p.get(), good);
});

test("falls back to the SDK token only when it is a JWT", async () => {
  const good = jwt(Math.floor(Date.now() / 1000) + 600);
  const ok = createTokenProvider({ fetchToken: async () => null, sdkToken: async () => good });
  assert.equal(await ok.get(), good);
  const bad = createTokenProvider({
    fetchToken: async () => null,
    sdkToken: async () => "opaque-session-token",
  });
  assert.equal(await bad.get(), null);
});

test("caches until near expiry and refreshes on force", async () => {
  let calls = 0;
  let t = 1_000_000;
  const p = createTokenProvider({
    now: () => t,
    fetchToken: async () => jwt(Math.floor(t / 1000) + 600 + calls++),
    sdkToken: async () => null,
  });
  const a = await p.get();
  assert.equal(await p.get(), a);
  assert.equal(calls, 1);
  assert.notEqual(await p.get(true), a);
  t += 600_000;
  await p.get();
  assert.equal(calls, 3);
});
