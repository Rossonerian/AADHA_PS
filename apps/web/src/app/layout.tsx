import type { Metadata } from "next";
import localFont from "next/font/local";
import { InkProvider } from "@/lib/ink/react";
import "./globals.css";

const plexMono = localFont({
  src: [
    {
      path: "../../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff2",
      weight: "500",
      style: "normal",
    },
  ],
  display: "swap",
  variable: "--font-plex-mono",
  fallback: ["ui-monospace", "SF Mono", "Menlo", "monospace"],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : "https://aadha-ps.vercel.app",
  ),
  title: "PaisaProof",
  description:
    "Learn to judge financial claims. PaisaProof teaches calibration and checks tips, and never tells you what to buy or sell.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`plex-mono ${plexMono.variable}`}>
      <body className="min-h-screen antialiased">
        <InkProvider textures={false}>{children}</InkProvider>
      </body>
    </html>
  );
}
