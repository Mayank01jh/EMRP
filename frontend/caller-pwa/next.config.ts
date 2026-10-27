/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "https://emrp.onrender.com/api/v1",
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || "wss://emrp.onrender.com/api/v1",
  },
};

export default nextConfig;
