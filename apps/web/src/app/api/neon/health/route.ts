import { NextResponse } from "next/server";
import { getDatabaseName, isDatabaseConfigured, queryDb } from "@/lib/neon-db";
import { isNeonAuthConfigured } from "@/lib/neon-auth";
import { isRealtimeConfigured, sealJobRunsQuery } from "@/lib/neon-realtime";
import { DEFAULT_ASSETS_BUCKET, getStorageClient, isStorageConfigured } from "@/lib/neon-storage";

export const dynamic = "force-dynamic";

async function checkPostgres() {
  if (!isDatabaseConfigured()) {
    return { ok: false, error: "DATABASE_URL is not configured" };
  }

  try {
    const result = await queryDb<{ ok: number; db_name: string }>(
      "SELECT 1 AS ok, current_database() AS db_name",
    );
    const row = result.rows[0];
    return {
      ok: row?.ok === 1,
      dbName: row?.db_name ?? getDatabaseName(),
    };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Postgres check failed",
    };
  }
}

async function checkAuth() {
  const baseUrl = process.env.NEON_AUTH_BASE_URL?.trim();
  const jwksUrl = process.env.NEON_AUTH_JWKS_URL?.trim();
  const baseUrlConfigured = Boolean(baseUrl);
  const jwksUrlConfigured = Boolean(jwksUrl);
  const cookieSecretConfigured = isNeonAuthConfigured();

  if (!baseUrl || !jwksUrl) {
    return {
      ok: false,
      baseUrlConfigured,
      jwksUrlConfigured,
      cookieSecretConfigured,
      error: "NEON_AUTH_BASE_URL or NEON_AUTH_JWKS_URL is not configured",
    };
  }

  try {
    const response = await fetch(jwksUrl, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    const payload = (await response.json().catch(() => null)) as { keys?: unknown[] } | null;
    const keyCount = Array.isArray(payload?.keys) ? payload.keys.length : 0;

    return {
      ok: response.status === 200 && keyCount > 0,
      baseUrlConfigured,
      jwksUrlConfigured,
      cookieSecretConfigured,
      jwksStatus: response.status,
      keyCount,
      ...(response.status !== 200 || keyCount === 0
        ? { error: "JWKS endpoint did not return valid JWK keys" }
        : {}),
    };
  } catch (error) {
    return {
      ok: false,
      baseUrlConfigured,
      jwksUrlConfigured,
      cookieSecretConfigured,
      error: error instanceof Error ? error.message : "JWKS fetch failed",
    };
  }
}

function checkObjectStorage() {
  const endpointConfigured = Boolean(process.env.AWS_ENDPOINT_URL_S3?.trim());
  const region = process.env.AWS_REGION?.trim() || null;
  const credentialsConfigured = Boolean(
    process.env.AWS_ACCESS_KEY_ID?.trim() && process.env.AWS_SECRET_ACCESS_KEY?.trim(),
  );

  if (!isStorageConfigured()) {
    return {
      ok: false,
      bucket: DEFAULT_ASSETS_BUCKET,
      endpointConfigured,
      region,
      credentialsConfigured,
      error: "Object storage environment variables are incomplete",
    };
  }

  try {
    getStorageClient(DEFAULT_ASSETS_BUCKET);
    return {
      ok: true,
      bucket: DEFAULT_ASSETS_BUCKET,
      endpointConfigured,
      region,
      credentialsConfigured,
    };
  } catch (error) {
    return {
      ok: false,
      bucket: DEFAULT_ASSETS_BUCKET,
      endpointConfigured,
      region,
      credentialsConfigured,
      error: error instanceof Error ? error.message : "Storage client init failed",
    };
  }
}

async function checkRealtime() {
  const configured = isRealtimeConfigured();
  const db = getDatabaseName();

  if (!configured) {
    return {
      ok: false,
      configured,
      db,
      sealed: false,
      error: "NEON_REALTIME_URL or NEON_REALTIME_SECRET is not configured",
    };
  }

  try {
    const sealed = await sealJobRunsQuery();
    return {
      ok: true,
      configured,
      db,
      sealed: true,
      queryFingerprint: sealed.queryFingerprint,
      expiresAt: sealed.expiresAt,
    };
  } catch (error) {
    return {
      ok: false,
      configured,
      db,
      sealed: false,
      error: error instanceof Error ? error.message : "Realtime seal check failed",
    };
  }
}

export async function GET(): Promise<Response> {
  const [postgres, auth, objectStorage, realtime] = await Promise.all([
    checkPostgres(),
    checkAuth(),
    Promise.resolve(checkObjectStorage()),
    checkRealtime(),
  ]);

  const ok = postgres.ok && auth.ok && objectStorage.ok && realtime.ok;

  return NextResponse.json(
    {
      ok,
      services: {
        postgres,
        auth,
        objectStorage,
        realtime,
      },
    },
    {
      status: ok ? 200 : 503,
      headers: { "Cache-Control": "no-store" },
    },
  );
}
