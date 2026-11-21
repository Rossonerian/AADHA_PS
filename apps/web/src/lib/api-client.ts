import type {
  ApiErrorEnvelope,
  NasdaqChallengeResponse,
  NasdaqSubmitRequest,
  NasdaqSubmitResponse,
  UserLevel,
} from "./contracts";
import { authClient } from "./neon-auth-client";
import { createTokenProvider, fetchProxyToken } from "./auth-token";

const tokenProvider = createTokenProvider({
  fetchToken: fetchProxyToken,
  sdkToken: async () => {
    const client = authClient as typeof authClient & {
      getJWTToken?: () => Promise<string | null>;
    };
    return (await client.getJWTToken?.()) ?? null;
  },
});

export async function readToken(forceRefresh = false): Promise<string | null> {
  try {
    return await tokenProvider.get(forceRefresh);
  } catch {
    return null;
  }
}

// Fixtures are required lazily and only outside production, so the branch (and the
// mock-nasdaq module) is removed from production bundles.
/* eslint-disable @typescript-eslint/no-require-imports */
const mockNasdaq = (
  process.env.NODE_ENV !== "production" ? require("./mock-nasdaq") : null
) as typeof import("./mock-nasdaq");
/* eslint-enable @typescript-eslint/no-require-imports */

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requiredLevel?: UserLevel;
  readonly details?: unknown;

  constructor(
    status: number,
    code: string,
    message: string,
    requiredLevel?: UserLevel,
    details?: unknown,
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.requiredLevel = requiredLevel;
    this.details = details;
  }
}

export function getApiBaseUrl(): string {
  const configured =
    process.env.NEXT_PUBLIC_API_URL?.trim() || process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured && configured.length > 0) {
    const trimmed = configured.replace(/\/+$/, "");
    if (/^https?:\/\/[^/]+$/i.test(trimmed)) {
      return `${trimmed}/api/v1`;
    }
    return trimmed;
  }
  return "/api/v1";
}

export interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  token?: string | null;
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
}

function buildUrl(
  path: string,
  query?: Record<string, string | number | boolean | null | undefined>,
): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const baseUrl = getApiBaseUrl();
  const fullPath = `${baseUrl}${normalizedPath}`;

  if (!query) {
    return fullPath;
  }

  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) {
      searchParams.set(key, String(value));
    }
  }

  const qs = searchParams.toString();
  if (!qs) {
    return fullPath;
  }
  return fullPath.includes("?") ? `${fullPath}&${qs}` : `${fullPath}?${qs}`;
}

function isApiErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  if (typeof record.error !== "object" || record.error === null) {
    return false;
  }
  const err = record.error as Record<string, unknown>;
  return typeof err.code === "string" && typeof err.message === "string";
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { token, body, query, headers: customHeaders, ...init } = options;
  const headers = new Headers(customHeaders);

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const sessionToken =
    token === undefined && !headers.has("Authorization") ? await readToken() : token;
  if (sessionToken) {
    headers.set("Authorization", `Bearer ${sessionToken}`);
  }

  let serializedBody: BodyInit | undefined;
  if (body !== undefined) {
    if (typeof FormData !== "undefined" && body instanceof FormData) {
      serializedBody = body;
    } else if (typeof body === "string") {
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      serializedBody = body;
    } else {
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      serializedBody = JSON.stringify(body);
    }
  }

  const response = await fetch(buildUrl(path, query), {
    ...init,
    headers,
    body: serializedBody,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");

  let parsedBody: unknown = undefined;
  if (isJson) {
    parsedBody = await response.json().catch(() => undefined);
  } else {
    const text = await response.text().catch(() => "");
    parsedBody = text.length > 0 ? text : undefined;
  }

  if (!response.ok) {
    if (isApiErrorEnvelope(parsedBody)) {
      throw new ApiClientError(
        response.status,
        parsedBody.error.code,
        parsedBody.error.message,
        parsedBody.error.required_level,
        parsedBody,
      );
    }

    const bare = parsedBody as { code?: unknown; required_level?: unknown } | undefined;
    if (bare && typeof bare === "object" && typeof bare.code === "string") {
      throw new ApiClientError(
        response.status,
        bare.code,
        bare.code === "TOOL_LOCKED"
          ? "This tool is not unlocked yet."
          : `Request failed with status ${response.status}`,
        typeof bare.required_level === "number" ? (bare.required_level as UserLevel) : undefined,
        parsedBody,
      );
    }

    throw new ApiClientError(
      response.status,
      "HTTP_ERROR",
      `Request failed with status ${response.status}`,
      undefined,
      parsedBody,
    );
  }

  return parsedBody as T;
}

/**
 * Nasdaq verifier helpers. The server enforces the unlock gate (403 TOOL_LOCKED).
 * Mock (SYNTHETIC) data is used only when the backend or Finnhub key is absent, never on 403.
 */
function isBackendAbsent(err: unknown): boolean {
  if (err instanceof ApiClientError) {
    return err.code === "FINNHUB_UNAVAILABLE" || err.status === 404 || err.status === 502;
  }
  return err instanceof TypeError; // network failure
}

export async function getNasdaqChallenge(
  symbol: string,
  token?: string | null,
): Promise<NasdaqChallengeResponse> {
  if (process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_USE_MOCKS === "true") {
    // Dev-only: mock mode has no backend, so skip the request (avoids a console 404).
    return mockNasdaq.mockNasdaqChallenge(symbol);
  }
  try {
    return await apiFetch<NasdaqChallengeResponse>("/nasdaq-verifier/challenge", {
      token,
      query: { symbol },
    });
  } catch (err) {
    if (process.env.NODE_ENV !== "production" && isBackendAbsent(err)) {
      return mockNasdaq.mockNasdaqChallenge(symbol);
    }
    throw err;
  }
}

export async function submitNasdaqVerifier(
  req: NasdaqSubmitRequest,
  token?: string | null,
): Promise<NasdaqSubmitResponse> {
  if (
    process.env.NODE_ENV !== "production" &&
    process.env.NEXT_PUBLIC_USE_MOCKS === "true" &&
    req.challenge_id.startsWith("mock_")
  ) {
    return mockNasdaq.mockNasdaqSubmit(req);
  }
  return apiFetch<NasdaqSubmitResponse>("/nasdaq-verifier/submit", {
    method: "POST",
    token,
    body: req,
  });
}
