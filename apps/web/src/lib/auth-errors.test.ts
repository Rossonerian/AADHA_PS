import assert from "node:assert/strict";
import test from "node:test";
import { classifyAuthError } from "./auth-errors.ts";

test("wrong password is not treated as an unknown user", () => {
  const r = classifyAuthError({
    code: "INVALID_EMAIL_OR_PASSWORD",
    message: "Invalid email or password",
    status: 401,
  });
  assert.equal(r.kind, "invalid_credentials");
});

test("existing email on sign-up maps to already_exists", () => {
  const r = classifyAuthError({
    code: "USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL",
    message: "User already exists. Use another email.",
  });
  assert.equal(r.kind, "already_exists");
});

test("google provider missing gives a friendly message", () => {
  const r = classifyAuthError({ status: 404, message: "Provider not found" }, "google");
  assert.equal(r.kind, "provider_unavailable");
  assert.match(r.message, /Use your email/);
});

test("google unconfigured 503 from the proxy route is friendly", () => {
  const r = classifyAuthError(
    { status: 503, code: "AUTH_NOT_CONFIGURED", message: "Neon Auth is not configured" },
    "google",
  );
  assert.equal(r.kind, "provider_unavailable");
});

test("network failures and rate limits", () => {
  assert.equal(classifyAuthError(new TypeError("Failed to fetch")).kind, "network");
  assert.equal(classifyAuthError({ status: 429, message: "x" }).kind, "rate_limited");
});

test("unverified email", () => {
  assert.equal(
    classifyAuthError({ code: "EMAIL_NOT_VERIFIED", message: "Email not verified" }).kind,
    "email_not_verified",
  );
});

test("unknown errors keep their message", () => {
  assert.equal(classifyAuthError({ message: "Boom" }).message, "Boom");
});
