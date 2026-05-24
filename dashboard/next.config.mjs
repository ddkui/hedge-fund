/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produces a minimal standalone build for Docker
  output: 'standalone',

  async rewrites() {
    // In Docker, Caddy routes /api/* to the gateway directly.
    // This rewrite only applies in local dev (npm run dev).
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_GATEWAY_URL ?? 'http://localhost:8000'}/:path*`,
      },
    ]
  },
}

export default nextConfig
