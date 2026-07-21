import type { NextConfig } from "next";
import path from "path";

// In development we run the Next.js dev server (port 3000) separately from the
// Python backend (port 8001), so we proxy /api/* to it via rewrites.
// For production we build a fully static site (`output: "export"` -> `out/`)
// that the Python backend serves itself on a single port. Rewrites are not
// supported in static export, so they are enabled only in development.
const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  output: "export",
  turbopack: {
    root: path.resolve(__dirname),
  },
  ...(isDev
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: "http://localhost:8001/api/:path*",
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
