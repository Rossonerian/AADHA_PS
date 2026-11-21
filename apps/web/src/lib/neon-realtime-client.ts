"use client";

import { createRealtimeClient, type RealtimeClient } from "@neon/realtime/client";

export const DEFAULT_NEON_REALTIME_URL =
  "wss://ep-misty-paper-azc60pot.rt.c-3.ap-southeast-1.aws.neon.tech/";

let cachedClient: RealtimeClient | null = null;

export function getNeonRealtimeUrl(): string {
  return process.env.NEXT_PUBLIC_NEON_REALTIME_URL?.trim() || DEFAULT_NEON_REALTIME_URL;
}

export function getRealtimeClientUrl(): string {
  return getNeonRealtimeUrl();
}

export function createAppRealtimeClient(): RealtimeClient {
  const url = getNeonRealtimeUrl();
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
