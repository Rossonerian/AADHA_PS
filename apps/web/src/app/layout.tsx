import type { Metadata } from "next";
import { InkProvider } from "@/lib/ink/react";
import "./globals.css";

export const metadata: Metadata = {
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
    <html lang="en">
      <body className="min-h-screen antialiased">
        <InkProvider textures={false}>{children}</InkProvider>
      </body>
    </html>
  );
}
