import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aacharya — Learn to read the market",
  description: "A friendly learning space to build confidence with financial information.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
