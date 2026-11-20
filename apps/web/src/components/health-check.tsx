"use client";

import { useState } from "react";
import { Alert, Button, Panel } from "@/components/ui";
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
    <Panel className="mt-6 health-check-panel">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-medium text-gray-700">API Health Check</h2>
        <Button
          variant="secondary"
          type="button"
          onClick={runCheck}
          disabled={state.status === "loading"}
          className="h-auto min-h-8 px-3 py-1.5 text-xs"
        >
          {state.status === "loading" ? "Checking..." : "Ping /api/v1/health"}
        </Button>
      </div>
      {state.status === "ok" && (
        <Alert className="mt-2 text-xs" variant="success" role="status">
          Status: {state.data.status} (v{state.data.version}, db: {state.data.db}, market as of:{" "}
          {state.data.market_data_as_of ?? "n/a"})
        </Alert>
      )}
      {state.status === "error" && (
        <Alert className="mt-2 text-xs" variant="warning" role="alert">
          Backend unreachable or returned error: {state.message}
        </Alert>
      )}
    </Panel>
  );
}
