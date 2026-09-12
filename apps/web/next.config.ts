import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    const api = process.env.WALLY_DEV_API ?? "http://127.0.0.1:8000";
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/health/:path*", destination: `${api}/health/:path*` },
    ];
  },
};
export default config;
