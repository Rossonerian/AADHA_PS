import assert from "node:assert/strict";
import test from "node:test";
import { hasDetailAccess } from "./health-access.ts";

const req = (token?: string) =>
  new Request("http://localhost/api/neon/health", {
    headers: token === undefined ? {} : { "x-health-token": token },
  });

test("health detail requires a configured token and an exact match", () => {
  delete process.env.HEALTH_DETAIL_TOKEN;
  assert.equal(hasDetailAccess(req("anything")), false);
  assert.equal(hasDetailAccess(req("")), false);

  process.env.HEALTH_DETAIL_TOKEN = "s3cret-token";
  assert.equal(hasDetailAccess(req()), false);
  assert.equal(hasDetailAccess(req("wrong")), false);
  assert.equal(hasDetailAccess(req("s3cret-token-longer")), false);
  assert.equal(hasDetailAccess(req("s3cret-token")), true);
  delete process.env.HEALTH_DETAIL_TOKEN;
});
