"use client";

import { createRealtimeClient, type RealtimeClient } from "@neon/realtime/client";

let cachedClient: RealtimeClient | null = null;

export function getRealtimeClientUrl(): string {
  return process.env.NEXT_PUBLIC_NEON_REALTIME_URL?.trim() ?? "";
}

export function createAppRealtimeClient(): RealtimeClient {
  const url = getRealtimeClientUrl();
  if (!url) {
    throw new Error("NEXT_PUBLIC_NEON_REALTIME_URL is not configured");
  }
  return createRealtimeClient({ url });
}

export function getRealtimeClient(): RealtimeClient {
  if (!cachedClient) {
    cachedClient = createAppRealtimeClient();
  }
  return cachedClient;
}
