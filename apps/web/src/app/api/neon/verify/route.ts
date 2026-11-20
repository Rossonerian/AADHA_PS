import { NextResponse } from "next/server";
import type { MaterializedLiveQuerySubscription } from "@neon/realtime/client";
import { isDatabaseConfigured, queryDb } from "@/lib/neon-db";
import {
  closeRealtimeServer,
  getRealtimeServer,
  isRealtimeConfigured,
  latestJobRunsQuery,
  type JobRunRow,
} from "@/lib/neon-realtime";
import {
  assetExists,
  DEFAULT_ASSETS_BUCKET,
  deleteAsset,
  downloadAsset,
  getAssetUrl,
  isStorageConfigured,
  uploadAsset,
} from "@/lib/neon-storage";

export const dynamic = "force-dynamic";

type VerifyCheck = "storage" | "realtime" | "all";

function isVerifyCheck(value: unknown): value is VerifyCheck {
  return value === "storage" || value === "realtime" || value === "all";
}

async function runStorageVerification() {
  if (!isStorageConfigured()) {
    return {
      ok: false,
      error: "Object storage environment variables are not configured",
    };
  }

  const key = `_verify/${crypto.randomUUID()}.txt`;
  const expectedText = `neon-storage-verify-${crypto.randomUUID()}`;
  const expectedBytes = Buffer.from(expectedText, "utf8");
  let uploaded = false;
  let cleanupAttempted = false;

  try {
    await uploadAsset(key, expectedBytes, {
      contentType: "text/plain; charset=utf-8",
    });
    uploaded = true;

    const existsAfterUpload = await assetExists(key);
    if (!existsAfterUpload) {
      throw new Error("Uploaded verification asset reported missing by exists()");
    }

    const downloaded = await downloadAsset(key);
    const downloadedBytes = Buffer.from(await downloaded.arrayBuffer());
    if (!downloadedBytes.equals(expectedBytes)) {
      throw new Error("Downloaded bytes did not match uploaded payload");
    }

    const presignedUrl = await getAssetUrl(key, { expiresIn: 60 });
    const presignedRes = await fetch(presignedUrl, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (!presignedRes.ok) {
      throw new Error(`Presigned URL fetch returned HTTP ${presignedRes.status}`);
    }

    const presignedBytes = Buffer.from(await presignedRes.arrayBuffer());
    if (!presignedBytes.equals(expectedBytes)) {
      throw new Error("Presigned URL bytes did not match uploaded payload");
    }

    cleanupAttempted = true;
    await deleteAsset(key);
    const cleanedUp = !(await assetExists(key));

    return {
      ok: cleanedUp,
      bucket: DEFAULT_ASSETS_BUCKET,
      key,
      bytesVerified: expectedBytes.byteLength,
      presignedStatus: presignedRes.status,
      cleanedUp,
      ...(cleanedUp ? {} : { error: "Verification asset still existed after delete" }),
    };
  } catch (error) {
    return {
      ok: false,
      bucket: DEFAULT_ASSETS_BUCKET,
      key,
      error: error instanceof Error ? error.message : "Storage verification failed",
    };
  } finally {
    if (uploaded && !cleanupAttempted) {
      try {
        await deleteAsset(key);
      } catch (cleanupError) {
        console.error(
          "[neon-verify] Failed to clean up verification object:",
          cleanupError instanceof Error ? cleanupError.message : String(cleanupError),
        );
      }
    }
  }
}

function waitForLiveState(
  subscription: MaterializedLiveQuerySubscription<JobRunRow>,
  timeoutMs: number,
): Promise<void> {
  const initialState = subscription.getState();
  if (initialState.status === "live") {
    return Promise.resolve();
  }
  if (initialState.status === "error") {
    return Promise.reject(initialState.error);
  }
  if (initialState.status === "closed") {
    return Promise.reject(new Error("Realtime subscription closed before becoming live"));
  }

  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      unsubscribeState();
      reject(new Error(`Timed out waiting for realtime subscription live state (${timeoutMs}ms)`));
    }, timeoutMs);

    const unsubscribeState = subscription.onStateChange((state) => {
      if (state.status === "live") {
        clearTimeout(timer);
        unsubscribeState();
        resolve();
      } else if (state.status === "error") {
        clearTimeout(timer);
        unsubscribeState();
        reject(state.error);
      } else if (state.status === "closed") {
        clearTimeout(timer);
        unsubscribeState();
        reject(new Error("Realtime subscription closed unexpectedly"));
      }
    });
  });
}

async function runRealtimeVerification() {
  if (!isDatabaseConfigured()) {
    return { ok: false, error: "DATABASE_URL is not configured" };
  }
  if (!isRealtimeConfigured()) {
    return { ok: false, error: "NEON_REALTIME_URL or NEON_REALTIME_SECRET is not configured" };
  }

  const markerJobName = `verify_${crypto.randomUUID()}`;
  let subscription: MaterializedLiveQuerySubscription<JobRunRow> | null = null;
  let unsubscribeUpdates: (() => void) | null = null;
  let insertedId: number | null = null;
  let changeEventObserved = false;
  let cleanedUp = false;

  try {
    const realtime = getRealtimeServer();
    subscription = await realtime.subscribe(latestJobRunsQuery());
    unsubscribeUpdates = subscription.onUpdate((update) => {
      if (update.type === "changes") {
        changeEventObserved = true;
      }
    });

    await waitForLiveState(subscription, 10_000);

    const insertResult = await queryDb<{ id: number }>(
      "INSERT INTO job_runs (job_name, status, market_data_as_of, details_json) VALUES ($1, $2, $3, $4) RETURNING id",
      [markerJobName, "verify_probe", null, "{}"],
    );
    insertedId = insertResult.rows[0]?.id ?? null;
    if (insertedId === null) {
      throw new Error("Insert into job_runs did not return an id");
    }

    await subscription.awaitRows(
      (rows) => rows.some((row) => row.id === insertedId && row.job_name === markerJobName),
      10_000,
    );

    await queryDb("DELETE FROM job_runs WHERE id = $1", [insertedId]);
    const deletedId = insertedId;
    insertedId = null;

    await subscription.awaitRows((rows) => !rows.some((row) => row.id === deletedId), 5_000);
    cleanedUp = true;

    return {
      ok: true,
      insertedId: deletedId,
      markerJobName,
      changeEventObserved,
      cleanedUp,
    };
  } catch (error) {
    return {
      ok: false,
      markerJobName,
      changeEventObserved,
      error: error instanceof Error ? error.message : "Realtime verification failed",
    };
  } finally {
    if (insertedId !== null) {
      try {
        await queryDb("DELETE FROM job_runs WHERE id = $1", [insertedId]);
      } catch (cleanupError) {
        console.error(
          "[neon-verify] Failed to delete throwaway job_runs row:",
          cleanupError instanceof Error ? cleanupError.message : String(cleanupError),
        );
      }
    }
    unsubscribeUpdates?.();
    subscription?.unsubscribe();
    closeRealtimeServer();
  }
}

export async function POST(request: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { ok: false, error: "Request body must be valid JSON with check: storage | realtime | all" },
      { status: 400 },
    );
  }

  const check =
    typeof body === "object" && body !== null ? (body as Record<string, unknown>).check : undefined;

  if (!isVerifyCheck(check)) {
    return NextResponse.json(
      { ok: false, error: 'Invalid "check" value. Expected "storage", "realtime", or "all".' },
      { status: 400 },
    );
  }

  const results: Record<string, unknown> = {};
  let allOk = true;

  if (check === "storage" || check === "all") {
    const storageResult = await runStorageVerification();
    results.storage = storageResult;
    if (!storageResult.ok) {
      allOk = false;
    }
  }

  if (check === "realtime" || check === "all") {
    const realtimeResult = await runRealtimeVerification();
    results.realtime = realtimeResult;
    if (!realtimeResult.ok) {
      allOk = false;
    }
  }

  return NextResponse.json(
    {
      ok: allOk,
      check,
      results,
    },
    {
      status: allOk ? 200 : 500,
      headers: { "Cache-Control": "no-store" },
    },
  );
}
