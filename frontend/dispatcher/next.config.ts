import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/dispatcher/:path*",
        destination: "/:path*",
      },
      {
        source: "/dispatcher",
        destination: "/",
      },
    ];
  },
};

export default nextConfig;
