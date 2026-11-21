import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import ts from "typescript";

function client() {
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
    process: { env: { NODE_ENV: "production" } },
    require(name) {
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

test("Nasdaq challenge, submit and unlock progress use the signed-in session", async () => {
  const { api, requests } = client();
  await api.getNasdaqChallenge("NDX");
  await api.submitNasdaqVerifier({ challenge_id: "challenge", answers: [] });
  await Promise.all(["/me", "/plan", "/me/dashboard"].map((path) => api.apiFetch(path)));
  assert.equal(requests.length, 5);
  for (const request of requests) {
    assert.equal(request.headers.get("Authorization"), "Bearer signed-in-token");
  }
  assert.equal(requests[0].url, "/api/v1/nasdaq-verifier/challenge?symbol=NDX");
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
