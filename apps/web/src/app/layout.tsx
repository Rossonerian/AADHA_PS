import type { Metadata } from "next";
import { InkProvider } from "@/lib/ink/react";
import "./globals.css";

export const metadata: Metadata = {
  title: "PaisaProof",
  description: "Investor literacy & claim verification platform — web scaffold",
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
