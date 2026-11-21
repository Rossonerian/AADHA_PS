import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import ts from "typescript";

function client(env = { NODE_ENV: "production" }) {
  const requests = [];
  const compiledModule = { exports: {} };
  const source = ts.transpileModule(
    readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8"),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } },
  ).outputText;
  vm.runInNewContext(source, {
    module: compiledModule,
    exports: compiledModule.exports,
    Headers,
    URLSearchParams,
    FormData,
    process: { env },
    require(name) {
      if (name === "./auth-token")
        return {
          fetchProxyToken: async () => "signed-in-token",
          createTokenProvider: ({ fetchToken }) => ({ get: fetchToken }),
        };
      if (name === "./mock-nasdaq") {
        return {};
      }
      assert.equal(name, "./neon-auth-client");
      return { authClient: { getJWTToken: async () => "signed-in-token" } };
    },
    fetch: async (url, init) => {
      requests.push({ url, ...init });
      return new Response("{}", { headers: { "content-type": "application/json" } });
    },
  });
  return { api: compiledModule.exports, requests };
}

function loadModule(relativePath, env = {}) {
  const compiledModule = { exports: {} };
  const source = ts.transpileModule(readFileSync(new URL(relativePath, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  vm.runInNewContext(source, {
    module: compiledModule,
    exports: compiledModule.exports,
    process: { env },
    require(name) {
      if (name === "@neon/auth/next/server") {
        return { createNeonAuth: (cfg) => ({ ...cfg, handler: () => ({}) }) };
      }
      if (name === "@neon/realtime/client") {
        return { createRealtimeClient: (cfg) => ({ ...cfg }) };
      }
      return {};
    },
  });
  return compiledModule.exports;
}

test("Nasdaq challenge, submit and unlock progress use the signed-in session", async () => {
  const { api, requests } = client();
  await api.getNasdaqChallenge("NDX");
  await api.submitNasdaqVerifier({ challenge_id: "challenge", answers: [] });
  await Promise.all(["/me", "/plan", "/me/dashboard"].map((path) => api.apiFetch(path)));
  assert.equal(requests.length, 5);
  for (const request of requests) {
    assert.equal(request.headers.get("Authorization"), "Bearer signed-in-token");
  }
  assert.equal(
    requests[0].url,
    "https://aadha-ps.onrender.com/api/v1/nasdaq-verifier/challenge?symbol=NDX",
  );
  assert.equal(requests[1].method, "POST");
});

test("explicit tokens, anonymous requests and custom authorization are preserved", async () => {
  const { api, requests } = client();
  await api.apiFetch("/me", { token: "explicit" });
  await api.apiFetch("/health", { token: null });
  await api.apiFetch("/me", { headers: { Authorization: "Bearer custom" } });
  assert.equal(requests[0].headers.get("Authorization"), "Bearer explicit");
  assert.equal(requests[1].headers.get("Authorization"), null);
  assert.equal(requests[2].headers.get("Authorization"), "Bearer custom");
});

test("api client getApiBaseUrl falls back to Render backend in production and relative in dev", () => {
  const prodClient = client({ NODE_ENV: "production" });
  assert.equal(prodClient.api.getApiBaseUrl(), "https://aadha-ps.onrender.com/api/v1");

  const devClient = client({ NODE_ENV: "development" });
  assert.equal(devClient.api.getApiBaseUrl(), "/api/v1");

  const customClient = client({
    NODE_ENV: "production",
    NEXT_PUBLIC_API_URL: "https://custom.api.example.com",
  });
  assert.equal(customClient.api.getApiBaseUrl(), "https://custom.api.example.com/api/v1");
});

test("neon auth provides zero-config fallbacks for baseUrl and cookie secret", () => {
  const authModule = loadModule("../src/lib/neon-auth.ts", {});
  assert.equal(authModule.isNeonAuthConfigured(), true);
  assert.equal(authModule.DEFAULT_NEON_AUTH_BASE_URL.includes("neonauth"), true);
  assert.equal(authModule.DEFAULT_NEON_AUTH_COOKIE_SECRET.length >= 32, true);

  const neonAuth = authModule.getNeonAuth();
  assert.ok(neonAuth);
});

test("neon realtime client provides zero-config fallback WebSocket URL", () => {
  const rtModule = loadModule("../src/lib/neon-realtime-client.ts", {});
  assert.equal(rtModule.DEFAULT_NEON_REALTIME_URL.startsWith("wss://"), true);
  assert.equal(rtModule.getNeonRealtimeUrl(), rtModule.DEFAULT_NEON_REALTIME_URL);
  assert.equal(rtModule.getRealtimeClientUrl(), rtModule.DEFAULT_NEON_REALTIME_URL);
});
