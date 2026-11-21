import { createNeonAuth, type NeonAuth } from "@neon/auth/next/server";

export type NeonAuthHandlers = ReturnType<NeonAuth["handler"]>;

export const DEFAULT_NEON_AUTH_BASE_URL =
  "https://ep-misty-paper-azc60pot.neonauth.c-3.ap-southeast-1.aws.neon.tech/neondb/auth";
export const DEFAULT_NEON_AUTH_COOKIE_SECRET = "Og7KpaaFTr+RObMeqpks0WuYOBcslAPp8bt4MbH3D5w=";

let cachedAuth: NeonAuth | null = null;
let cachedHandlers: NeonAuthHandlers | null = null;

export function isNeonAuthConfigured(): boolean {
  const baseUrl = process.env.NEON_AUTH_BASE_URL?.trim() || DEFAULT_NEON_AUTH_BASE_URL;
  const secret = process.env.NEON_AUTH_COOKIE_SECRET?.trim() || DEFAULT_NEON_AUTH_COOKIE_SECRET;
  return Boolean(baseUrl && secret && secret.length >= 32);
}

export function getNeonAuth(): NeonAuth {
  if (cachedAuth) {
    return cachedAuth;
  }

  const baseUrl = process.env.NEON_AUTH_BASE_URL?.trim() || DEFAULT_NEON_AUTH_BASE_URL;
  if (!baseUrl) {
    throw new Error("NEON_AUTH_BASE_URL is not configured");
  }

  const secret = process.env.NEON_AUTH_COOKIE_SECRET?.trim() || DEFAULT_NEON_AUTH_COOKIE_SECRET;
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
