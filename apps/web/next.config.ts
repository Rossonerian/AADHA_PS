import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

/** Reduce a URL-ish env value to its origin (scheme://host[:port]); empty if invalid. */
function originOf(value: string | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) return "";
  try {
    return new URL(trimmed).origin;
  } catch {
    return "";
  }
}

function buildCsp(): string {
  // Origins are resolved when the config loads (build time on Vercel), so set them there.
  const apiOrigin = originOf(
    process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_URL,
  );
  const neonAuthOrigin = originOf(process.env.NEON_AUTH_BASE_URL);
  const realtimeOrigin = originOf(process.env.NEXT_PUBLIC_NEON_REALTIME_URL);
  const connect = [
    "'self'",
    apiOrigin,
    neonAuthOrigin,
    realtimeOrigin,
    "https://accounts.google.com",
    "https://vitals.vercel-insights.com",
    ...(isDev ? ["ws:", "http://localhost:*"] : []),
  ].filter(Boolean);

  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    // Next.js injects inline bootstrap/RSC flight scripts; a nonce-free policy therefore
    // needs 'unsafe-inline' for scripts (see PR notes for the tradeoff).
    "script-src": [
      "'self'",
      "'unsafe-inline'",
      "https://va.vercel-scripts.com",
      ...(isDev ? ["'unsafe-eval'"] : []),
    ],
    "style-src": ["'self'", "'unsafe-inline'", "https://kevintngo.github.io"],
    "font-src": ["'self'", "data:", "https://kevintngo.github.io"],
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "connect-src": connect,
    "frame-src": ["https://accounts.google.com"],
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'", "https://accounts.google.com"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
    ...(isDev ? {} : { "upgrade-insecure-requests": [] }),
  };

  return Object.entries(directives)
    .map(([name, values]) => [name, ...values].join(" "))
    .join("; ");
}

const securityHeaders = [
  { key: "Content-Security-Policy", value: buildCsp() },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_COMMIT_SHA: process.env.NEXT_PUBLIC_COMMIT_SHA ?? process.env.VERCEL_GIT_COMMIT_SHA,
  },
  experimental: {
    optimizePackageImports: ["recharts", "lucide-react", "radix-ui"],
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
