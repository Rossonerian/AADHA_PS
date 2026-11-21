/**
 * Resolves the short-lived JWT that the PaisaProof API expects as a Bearer token.
 *
 * `@neon/auth`'s `getJWTToken()` returns `session.token`. That is a real JWT only when
 * the `/get-session` response came straight from Neon Auth (it carries a `set-auth-jwt`
 * header). When the Next proxy answers from its signed `session_data` cookie, which is
 * the normal case right after the OAuth redirect and on every reload, no such header
 * exists and `session.token` is the opaque session token, which the API rejects with
 * 401. The `/token` endpoint always returns a signed JWT for the current session, so use
 * it as the source of truth. Pure (no framework imports) so it can be unit tested.
 */

const EXPIRY_SAFETY_MS = 30_000;

export function isJwtShaped(value: unknown): value is string {
  return typeof value === "string" && /^[\w-]+\.[\w-]+\.[\w-]*$/.test(value);
}

/** Expiry of a JWT in epoch milliseconds, or null when it cannot be read. */
export function jwtExpiryMs(token: string): number | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = JSON.parse(
      new TextDecoder().decode(Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))),
    ) as { exp?: unknown };
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

export type TokenProviderDeps = {
  /** GET /api/auth/token through the Neon Auth proxy; resolves to the JWT or null. */
  fetchToken: () => Promise<string | null>;
  /** Fallback: the SDK's `getJWTToken()` (may be an opaque session token). */
  sdkToken: () => Promise<string | null>;
  now?: () => number;
};

export function createTokenProvider(deps: TokenProviderDeps) {
  const now = deps.now ?? Date.now;
  let cached: { token: string; expiresAt: number } | null = null;
  let inflight: Promise<string | null> | null = null;

  async function resolve(): Promise<string | null> {
    for (const source of [deps.fetchToken, deps.sdkToken]) {
      try {
        const token = await source();
        if (isJwtShaped(token)) {
          cached = { token, expiresAt: jwtExpiryMs(token) ?? now() + 60_000 };
          return token;
        }
      } catch {
        // try the next source
      }
    }
    return null;
  }

  return {
    /** Returns a JWT; `forceRefresh` skips the cache (use after a 401). */
    async get(forceRefresh = false): Promise<string | null> {
      if (!forceRefresh && cached && cached.expiresAt - EXPIRY_SAFETY_MS > now()) {
        return cached.token;
      }
      inflight ??= resolve().finally(() => {
        inflight = null;
      });
      return inflight;
    },
    clear() {
      cached = null;
    },
  };
}

export async function fetchProxyToken(): Promise<string | null> {
  const res = await fetch("/api/auth/token", {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) return null;
  const body = (await res.json().catch(() => null)) as { token?: unknown } | null;
  return isJwtShaped(body?.token) ? body.token : null;
}
