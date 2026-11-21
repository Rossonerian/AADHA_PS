import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "PaisaProof",
    short_name: "PaisaProof",
    description:
      "Learn to judge financial claims. PaisaProof teaches calibration and checks tips, and never tells you what to buy or sell.",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f3ea",
    theme_color: "#1f4d3a",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
      {
        src: "/apple-icon.png",
        sizes: "180x180",
        type: "image/png",
      },
      {
        src: "/favicon.ico",
        sizes: "48x48 32x32 16x16",
        type: "image/x-icon",
      },
    ],
  };
}
