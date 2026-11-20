import type { ApiErrorEnvelope, UserLevel } from "./contracts";

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
    return configured.replace(/\/+$/, "");
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

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
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
