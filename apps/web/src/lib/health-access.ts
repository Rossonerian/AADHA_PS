import { timingSafeEqual } from "node:crypto";

/**
 * Constant-time check of the `x-health-token` header against HEALTH_DETAIL_TOKEN.
 * Without a configured token, detailed diagnostics are never exposed.
 */
export function hasDetailAccess(request: Request): boolean {
  const expected = process.env.HEALTH_DETAIL_TOKEN?.trim();
  const provided = request.headers.get("x-health-token") ?? "";
  if (!expected || !provided) return false;
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
