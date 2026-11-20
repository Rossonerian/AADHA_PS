import { attachDatabasePool } from "@vercel/functions";
import { Pool, type QueryResult, type QueryResultRow } from "pg";

const globalForNeonDb = globalThis as typeof globalThis & {
  __neonPgPool?: Pool;
};

function normalizeDatabaseUrl(rawUrl: string): string {
  try {
    const parsed = new URL(rawUrl);
    if (parsed.searchParams.get("sslmode") === "require") {
      parsed.searchParams.set("sslmode", "verify-full");
    }
    return parsed.toString();
  } catch {
    return rawUrl.replace(/([?&]sslmode=)require(&|$)/i, "$1verify-full$2");
  }
}

export function isDatabaseConfigured(): boolean {
  return Boolean(process.env.DATABASE_URL?.trim());
}

export function getDatabaseName(): string {
  const rawUrl = process.env.DATABASE_URL?.trim();
  if (!rawUrl) {
    return "neondb";
  }

  try {
    const parsed = new URL(rawUrl);
    const dbName = parsed.pathname.replace(/^\/+/, "");
    return dbName.length > 0 ? dbName : "neondb";
  } catch {
    return "neondb";
  }
}

export function getPool(): Pool {
  if (globalForNeonDb.__neonPgPool) {
    return globalForNeonDb.__neonPgPool;
  }

  const rawUrl = process.env.DATABASE_URL?.trim();
  if (!rawUrl) {
    throw new Error("DATABASE_URL is not configured");
  }

  const pool = new Pool({
    connectionString: normalizeDatabaseUrl(rawUrl),
    max: 10,
    idleTimeoutMillis: 10_000,
    connectionTimeoutMillis: 10_000,
  });

  pool.on("error", (error: Error) => {
    console.error("[neon-db] Idle pool error:", error.message);
  });

  try {
    attachDatabasePool(pool);
  } catch (error) {
    console.warn(
      "[neon-db] attachDatabasePool skipped:",
      error instanceof Error ? error.message : String(error),
    );
  }

  globalForNeonDb.__neonPgPool = pool;
  return pool;
}

export async function queryDb<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params?: readonly unknown[],
): Promise<QueryResult<T>> {
  const pool = getPool();
  return pool.query<T>(text, params ? [...params] : undefined);
}
