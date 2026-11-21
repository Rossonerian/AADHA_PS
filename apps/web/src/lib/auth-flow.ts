/**
 * Pure decision logic for the Google sign-in vs sign-up flow.
 *
 * Neon Auth (managed Better Auth) has no switch to disable implicit sign-up for social
 * providers, so a Google sign-in for an unknown email always creates the account. We detect
 * that after the OAuth callback and, when the user came from "Sign in", ask before continuing.
 * Kept free of framework imports so it can be tested with `npm run test:unit`.
 */

export type AuthIntent = "signin" | "signup";
export type GoogleOutcome = "enter" | "confirm_create" | "welcome_back";

/** An account created this recently, in the same OAuth round trip, counts as brand new. */
export const FRESH_ACCOUNT_WINDOW_MS = 60_000;

export const AUTH_INTENT_KEY = "pp:auth-intent";
export const WELCOME_BACK_KEY = "pp:welcome-back";
export const DECLINED_EMAILS_KEY = "pp:google-declined";

export function parseIntent(raw: string | null | undefined): AuthIntent {
  return raw === "signup" ? "signup" : "signin";
}

export function isFreshAccount(
  createdAt: string | number | Date | null | undefined,
  now: number = Date.now(),
  windowMs: number = FRESH_ACCOUNT_WINDOW_MS,
): boolean {
  if (createdAt === null || createdAt === undefined) return false;
  const created = new Date(createdAt).getTime();
  if (!Number.isFinite(created)) return false;
  const age = now - created;
  return age >= -5_000 && age <= windowMs;
}

export function isNewGoogleUser(input: {
  newUserParam: boolean;
  createdAt?: string | number | Date | null;
  now?: number;
  previouslyDeclined?: boolean;
}): boolean {
  return (
    input.newUserParam ||
    Boolean(input.previouslyDeclined) ||
    isFreshAccount(input.createdAt, input.now)
  );
}

export function decideGoogleOutcome(input: {
  intent: AuthIntent;
  isNewUser: boolean;
}): GoogleOutcome {
  if (input.intent === "signin") {
    return input.isNewUser ? "confirm_create" : "enter";
  }
  return input.isNewUser ? "enter" : "welcome_back";
}

/** Messages for `?error=` values that Better Auth appends to the error callback URL. */
export function describeOAuthUrlError(code: string, description = ""): string {
  const key = code
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
  switch (key) {
    case "account_not_linked":
      return "This email already has a PaisaProof account with a password. Sign in with your email and password.";
    case "access_denied":
    case "state_mismatch":
    case "invalid_state":
    case "state_not_found":
      return "Sign-in was cancelled or expired, try again.";
    case "signup_disabled":
    case "signup disabled":
      return "New accounts cannot be created right now.";
    default: {
      const detail = description.trim();
      return detail
        ? `Sign-in did not complete: ${detail}`
        : "Sign-in did not complete. Try again.";
    }
  }
}

export function readOAuthUrlError(search: string): string | null {
  const params = new URLSearchParams(search);
  const code = params.get("error");
  const description = params.get("error_description") ?? "";
  if (!code && !description) return null;
  return describeOAuthUrlError(code ?? "", description);
}

/** Returns the query string without OAuth error params (leading "?" only when non-empty). */
export function stripOAuthErrorParams(search: string): string {
  const params = new URLSearchParams(search);
  params.delete("error");
  params.delete("error_description");
  const rest = params.toString();
  return rest ? `?${rest}` : "";
}

export function addDeclinedEmail(list: string[], email: string): string[] {
  const normalized = email.trim().toLowerCase();
  if (!normalized || list.includes(normalized)) return list;
  return [...list, normalized].slice(-20);
}

export function removeDeclinedEmail(list: string[], email: string): string[] {
  const normalized = email.trim().toLowerCase();
  return list.filter((item) => item !== normalized);
}
