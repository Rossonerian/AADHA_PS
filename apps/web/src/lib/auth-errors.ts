/**
 * Pure helpers that turn Neon Auth / Better Auth errors into friendly, actionable copy.
 * Kept free of framework imports so they can be unit tested with `npm run test:unit`.
 */

export type AuthFailureKind =
  | "invalid_credentials"
  | "already_exists"
  | "provider_unavailable"
  | "email_not_verified"
  | "rate_limited"
  | "network"
  | "session_expired"
  | "other";

export type AuthFailure = { kind: AuthFailureKind; message: string };

/** Event dispatched on `window` when the API rejects a refreshed token (session is dead). */
export const AUTH_EXPIRED_EVENT = "pp:auth-expired";

export const SESSION_EXPIRED_MESSAGE = "Your session has expired. Please sign in again.";

function field(err: unknown, key: string): string {
  if (err && typeof err === "object" && key in err) {
    const value = (err as Record<string, unknown>)[key];
    if (typeof value === "string" || typeof value === "number") return String(value);
  }
  return "";
}

export function classifyAuthError(
  err: unknown,
  context: "email" | "google" = "email",
): AuthFailure {
  const code = field(err, "code").toUpperCase();
  const status = Number(field(err, "status")) || 0;
  const raw = field(err, "message").trim();
  const text = `${code} ${raw}`.toLowerCase();

  if (
    err instanceof TypeError ||
    /failed to fetch|networkerror|network request failed/.test(text)
  ) {
    return {
      kind: "network",
      message: "Could not reach the sign-in service. Check your connection and try again.",
    };
  }
  if (status === 429 || text.includes("too_many_requests") || text.includes("too many")) {
    return {
      kind: "rate_limited",
      message: "Too many attempts. Please wait a minute and try again.",
    };
  }
  if (code.includes("USER_ALREADY_EXISTS") || text.includes("already exists")) {
    return {
      kind: "already_exists",
      message: "An account with this email already exists. Sign in instead.",
    };
  }
  if (code.includes("EMAIL_NOT_VERIFIED") || text.includes("not verified")) {
    return {
      kind: "email_not_verified",
      message: "Verify your email first: check your inbox for the confirmation link.",
    };
  }
  if (
    context === "google" &&
    (status === 404 ||
      status === 503 ||
      status === 501 ||
      /provider|not configured|not enabled|client.?id|client.?secret|social/.test(text))
  ) {
    return {
      kind: "provider_unavailable",
      message: "Google sign-in is not available right now. Use your email to continue.",
    };
  }
  if (code.includes("INVALID_EMAIL_OR_PASSWORD") || text.includes("invalid email or password")) {
    // Better Auth deliberately does not reveal whether the email exists.
    return {
      kind: "invalid_credentials",
      message:
        "That email and password do not match. Check them, or create an account if you are new.",
    };
  }
  if (code === "AUTH_NOT_CONFIGURED" || status === 503) {
    return {
      kind: "provider_unavailable",
      message: "Sign-in is not configured on this deployment yet.",
    };
  }
  return { kind: "other", message: raw || "Authentication failed. Please try again." };
}
