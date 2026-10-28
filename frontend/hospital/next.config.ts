import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/hospital/:path*",
        destination: "/:path*",
      },
      {
        source: "/hospital",
        destination: "/",
      },
    ];
  },
};

export default nextConfig;
