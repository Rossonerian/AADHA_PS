"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/minor/skeleton";

// recharts is large; load it only when a chart is actually rendered.
const chartFallback = (height: number) =>
  function ChartFallback() {
    return <Skeleton className="w-full rounded-lg" style={{ height }} />;
  };

export const DashboardCharts = dynamic(
  () => import("@/components/charts").then((m) => m.DashboardCharts),
  { ssr: false, loading: chartFallback(320) },
);
export const ScenarioChart = dynamic(
  () => import("@/components/charts").then((m) => m.ScenarioChart),
  { ssr: false, loading: chartFallback(260) },
);
export const ExplainChart = dynamic(
  () => import("@/components/charts").then((m) => m.ExplainChart),
  { ssr: false, loading: chartFallback(260) },
);
export const CompareChart = dynamic(
  () => import("@/components/charts").then((m) => m.CompareChart),
  { ssr: false, loading: chartFallback(230) },
);
