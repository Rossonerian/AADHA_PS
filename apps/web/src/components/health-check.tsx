"use client";

import { useState } from "react";
import { ApiClientError, apiFetch } from "@/lib/api-client";
import type { HealthResponse } from "@/lib/contracts";

type CheckState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; data: HealthResponse }
  | { status: "error"; message: string };

export function HealthCheck() {
  const [state, setState] = useState<CheckState>({ status: "idle" });

  async function runCheck() {
    setState({ status: "loading" });
    try {
      const data = await apiFetch<HealthResponse>("/health");
      setState({ status: "ok", data });
    } catch (err) {
      if (err instanceof ApiClientError) {
        setState({ status: "error", message: `${err.code}: ${err.message}` });
      } else if (err instanceof Error) {
        setState({ status: "error", message: err.message });
      } else {
        setState({ status: "error", message: "Health check failed" });
      }
    }
  }

  return (
    <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between gap-4">
        <span className="text-sm font-medium text-gray-700">API Health Check</span>
        <button
          type="button"
          onClick={runCheck}
          disabled={state.status === "loading"}
          className="rounded-md bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {state.status === "loading" ? "Checking..." : "Ping /api/v1/health"}
        </button>
      </div>
      {state.status === "ok" && (
        <p className="mt-2 text-xs text-emerald-700">
          Status: {state.data.status} (v{state.data.version}, db: {state.data.db}, market as of:{" "}
          {state.data.market_data_as_of ?? "n/a"})
        </p>
      )}
      {state.status === "error" && (
        <p className="mt-2 text-xs text-amber-700">
          Backend unreachable or returned error: {state.message}
        </p>
      )}
    </div>
  );
}
