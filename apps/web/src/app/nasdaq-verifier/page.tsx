"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/minor/skeleton";

function NasdaqVerifierFallback() {
  return (
    <div
      className="space-y-4 py-2"
      role="status"
      aria-busy="true"
      aria-label="Loading Nasdaq verifier"
    >
      <div className="space-y-2">
        <Skeleton className="h-4 w-36" />
        <Skeleton className="h-8 w-64" />
      </div>
      <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5 space-y-4">
        <div className="flex flex-wrap gap-3">
          <Skeleton className="h-10 w-44" />
          <Skeleton className="h-10 w-28" />
        </div>
        <Skeleton className="h-52 w-full" />
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      </div>
    </div>
  );
}

const NasdaqVerifier = dynamic(
  () => import("@/components/nasdaq-verifier").then((mod) => mod.NasdaqVerifier),
  {
    ssr: false,
    loading: () => <NasdaqVerifierFallback />,
  },
);

export default function NasdaqVerifierPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <NasdaqVerifier />
    </main>
  );
}
