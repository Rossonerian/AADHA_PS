import { createNeonAuth, type NeonAuth } from "@neon/auth/next/server";

export type NeonAuthHandlers = ReturnType<NeonAuth["handler"]>;

let cachedAuth: NeonAuth | null = null;
let cachedHandlers: NeonAuthHandlers | null = null;

export function isNeonAuthConfigured(): boolean {
  const baseUrl = process.env.NEON_AUTH_BASE_URL?.trim();
  const secret = process.env.NEON_AUTH_COOKIE_SECRET?.trim();
  return Boolean(baseUrl && secret && secret.length >= 32);
}

export function getNeonAuth(): NeonAuth {
  if (cachedAuth) {
    return cachedAuth;
  }

  const baseUrl = process.env.NEON_AUTH_BASE_URL?.trim();
  if (!baseUrl) {
    throw new Error("NEON_AUTH_BASE_URL is not configured");
  }

  const secret = process.env.NEON_AUTH_COOKIE_SECRET?.trim();
  if (!secret || secret.length < 32) {
    throw new Error("NEON_AUTH_COOKIE_SECRET must be configured with at least 32 characters");
  }

  cachedAuth = createNeonAuth({
    baseUrl,
    cookies: { secret },
  });

  return cachedAuth;
}

export function getNeonAuthHandlers(): NeonAuthHandlers {
  if (!cachedHandlers) {
    cachedHandlers = getNeonAuth().handler();
  }
  return cachedHandlers;
}

export const auth: NeonAuth = new Proxy({} as NeonAuth, {
  get(_target, prop) {
    if (prop === "then") {
      return undefined;
    }
    const instance = getNeonAuth();
    const value = Reflect.get(instance, prop, instance);
    return typeof value === "function" ? value.bind(instance) : value;
  },
});
