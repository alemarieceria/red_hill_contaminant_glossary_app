import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",          // emit static HTML into ./out
  images: { unoptimized: true },  // no server means no on-demand image resizing
  trailingSlash: true,       // /pfas/ rather than /pfas — plays nicer with static hosts
};

export default nextConfig;
