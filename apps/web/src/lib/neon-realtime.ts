import type { MaterializedLiveQuerySubscription } from "@neon/realtime/client";
import {
  createRealtime,
  rawSql,
  type RawSqlQuery,
  type RealtimeDirectServer,
  type RealtimeServer,
  type SealedLiveQuery,
} from "@neon/realtime/server";
import { getDatabaseName } from "./neon-db";

export interface JobRunRow {
  id: number;
  job_name: string;
  status: string;
  market_data_as_of: string | null;
  ran_at: Date;
}

let cachedRealtimeServer: RealtimeDirectServer<RawSqlQuery<unknown>> | null = null;
let cachedRealtimeSealer: RealtimeServer<RawSqlQuery<unknown>> | null = null;

export function latestJobRunsQuery(): RawSqlQuery<JobRunRow> {
  return rawSql<JobRunRow>(
    "SELECT id, job_name, status, market_data_as_of, ran_at FROM job_runs ORDER BY id DESC LIMIT 10",
  );
}

export function isRealtimeConfigured(): boolean {
  return Boolean(process.env.NEON_REALTIME_URL?.trim() && process.env.NEON_REALTIME_SECRET?.trim());
}

export function getRealtimeServer(): RealtimeDirectServer<RawSqlQuery<unknown>> {
  if (cachedRealtimeServer) {
    return cachedRealtimeServer;
  }

  const url = process.env.NEON_REALTIME_URL?.trim();
  if (!url) {
    throw new Error("NEON_REALTIME_URL is not configured");
  }

  const secret = process.env.NEON_REALTIME_SECRET?.trim();
  if (!secret) {
    throw new Error("NEON_REALTIME_SECRET is not configured");
  }

  cachedRealtimeServer = createRealtime({
    url,
    secret,
    db: getDatabaseName(),
    debugMode: process.env.NODE_ENV !== "production",
  });

  return cachedRealtimeServer;
}

function getRealtimeSealer(): RealtimeServer<RawSqlQuery<unknown>> {
  if (process.env.NEON_REALTIME_URL?.trim()) {
    return getRealtimeServer();
  }

  if (cachedRealtimeSealer) {
    return cachedRealtimeSealer;
  }

  const secret = process.env.NEON_REALTIME_SECRET?.trim();
  if (!secret) {
    throw new Error("NEON_REALTIME_SECRET is not configured");
  }

  cachedRealtimeSealer = createRealtime({
    secret,
    db: getDatabaseName(),
    debugMode: process.env.NODE_ENV !== "production",
  });

  return cachedRealtimeSealer;
}

export function closeRealtimeServer(): void {
  if (cachedRealtimeServer) {
    cachedRealtimeServer.close();
    cachedRealtimeServer = null;
  }
}

export async function sealJobRunsQuery(): Promise<SealedLiveQuery<JobRunRow>> {
  return getRealtimeSealer().seal({ query: latestJobRunsQuery() });
}

export async function subscribeJobRuns(): Promise<MaterializedLiveQuerySubscription<JobRunRow>> {
  return getRealtimeServer().subscribe(latestJobRunsQuery());
}
