"use client";

import dynamic from "next/dynamic";
import { useSyncExternalStore } from "react";
import "./silk-background.css";

// Loaded lazily and client-only so the WebGL code stays out of the main bundle.
const Silk = dynamic(() => import("./silk"), { ssr: false });

const COMPACT_QUERY = "(max-width: 599.98px), (pointer: coarse)";

function subscribeCompact(onChange: () => void) {
  const query = window.matchMedia(COMPACT_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

const getCompact = () => window.matchMedia(COMPACT_QUERY).matches;
const getCompactServer = () => false;

const PALETTE = {
  dark: {
    color: "#1f4d3a",
    sheenColor: "#8fd1a9",
    lightMode: false,
    sheen: 0.28,
    glow: 0.1,
    depth: 0.6,
    noiseIntensity: 1,
  },
  light: {
    color: "#dcebe1",
    sheenColor: "#ffffff",
    lightMode: true,
    sheen: 0.3,
    glow: 0.1,
    depth: 0.4,
    noiseIntensity: 1,
  },
} as const;

/** Decorative, non-interactive silk backdrop for the auth screen. */
export function SilkBackground({ theme }: { theme: "light" | "dark" }) {
  const compact = useSyncExternalStore(subscribeCompact, getCompact, getCompactServer);
  const palette = PALETTE[theme];

  return (
    <div className="silk-background" data-theme={theme} aria-hidden="true">
      <Silk
        {...palette}
        speed={2}
        scale={1}
        fade={0.3}
        mouseInteraction={!compact}
        clickRipple={!compact}
      />
      <div className="silk-background-scrim" />
    </div>
  );
}
