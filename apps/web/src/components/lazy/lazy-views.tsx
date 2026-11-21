"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/minor/skeleton";

export const NasdaqVerifier = dynamic(
  () => import("@/components/nasdaq-verifier").then((m) => m.NasdaqVerifier),
  { ssr: false, loading: () => <Skeleton className="h-64 w-full rounded-lg" /> },
);
export const ProfilePanel = dynamic(
  () => import("@/components/auth/profile-panel").then((m) => m.ProfilePanel),
  { ssr: false, loading: () => <Skeleton className="h-64 w-full rounded-lg" /> },
);
