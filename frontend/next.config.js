/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    BUILD_ID: '2026-06-20-v10',
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'web-production-97eff.up.railway.app',
      },
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-97eff.up.railway.app'
    // fallback: App Router API routes (/api/admin, /api/auth/backend-sync) win first.
    return {
      fallback: [
        {
          source: '/api/:path*',
          destination: `${apiUrl}/api/:path*`,
        },
      ],
    }
  },
}

module.exports = nextConfig
