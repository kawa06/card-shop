/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    BUILD_ID: '2026-06-20-v5',
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'backend-production-054e.up.railway.app',
      },
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'https://backend-production-054e.up.railway.app/api/:path*',
      },
    ]
  },
}

module.exports = nextConfig
