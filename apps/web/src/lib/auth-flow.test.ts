import assert from "node:assert/strict";
import test from "node:test";
import {
  addDeclinedEmail,
  decideGoogleOutcome,
  describeOAuthUrlError,
  isFreshAccount,
  isNewGoogleUser,
  parseIntent,
  readOAuthUrlError,
  removeDeclinedEmail,
  stripOAuthErrorParams,
} from "./auth-flow.ts";

test("sign-in with an unknown Google account asks before creating", () => {
  assert.equal(decideGoogleOutcome({ intent: "signin", isNewUser: true }), "confirm_create");
});

test("sign-in with a known Google account enters directly", () => {
  assert.equal(decideGoogleOutcome({ intent: "signin", isNewUser: false }), "enter");
});

test("sign-up with a new Google account enters onboarding", () => {
  assert.equal(decideGoogleOutcome({ intent: "signup", isNewUser: true }), "enter");
});

test("sign-up with an existing Google account signs in with a welcome back", () => {
  assert.equal(decideGoogleOutcome({ intent: "signup", isNewUser: false }), "welcome_back");
});

test("intent defaults to signin for missing or unknown values", () => {
  assert.equal(parseIntent(null), "signin");
  assert.equal(parseIntent("garbage"), "signin");
  assert.equal(parseIntent("signup"), "signup");
});

test("fresh account detection uses a 60 second window", () => {
  const now = Date.parse("2026-11-21T10:00:00Z");
  assert.equal(isFreshAccount("2026-11-21T09:59:30Z", now), true);
  assert.equal(isFreshAccount("2026-11-21T09:58:00Z", now), false);
  assert.equal(isFreshAccount(undefined, now), false);
  assert.equal(isFreshAccount("not a date", now), false);
});

test("new user detection combines callback flag, createdAt and prior decline", () => {
  const now = Date.parse("2026-11-21T10:00:00Z");
  assert.equal(isNewGoogleUser({ newUserParam: true, now }), true);
  assert.equal(
    isNewGoogleUser({ newUserParam: false, createdAt: "2026-11-21T09:59:50Z", now }),
    true,
  );
  assert.equal(isNewGoogleUser({ newUserParam: false, previouslyDeclined: true, now }), true);
  assert.equal(
    isNewGoogleUser({ newUserParam: false, createdAt: "2026-01-01T00:00:00Z", now }),
    false,
  );
});

test("OAuth URL errors map to clear copy", () => {
  assert.match(describeOAuthUrlError("account_not_linked"), /email and password/);
  assert.match(describeOAuthUrlError("access_denied"), /cancelled or expired/);
  assert.match(describeOAuthUrlError("state_mismatch"), /cancelled or expired/);
  assert.match(describeOAuthUrlError("weird", "boom"), /boom/);
  assert.equal(readOAuthUrlError("?foo=1"), null);
  assert.match(readOAuthUrlError("?error=account_not_linked") ?? "", /password/);
});

test("OAuth error params are stripped from the URL, other params kept", () => {
  assert.equal(stripOAuthErrorParams("?error=access_denied&error_description=x"), "");
  assert.equal(stripOAuthErrorParams("?a=1&error=x"), "?a=1");
});

test("declined email list is normalized, deduplicated and removable", () => {
  let list = addDeclinedEmail([], " A@B.com ");
  list = addDeclinedEmail(list, "a@b.com");
  assert.deepEqual(list, ["a@b.com"]);
  assert.deepEqual(removeDeclinedEmail(list, "A@B.COM"), []);
});
