/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',

  // Timeout pour les requetes longues (5 minutes)
  experimental: {
    serverActions: {
      bodySizeLimit: '50mb',
    },
  },
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      // Exclure /api/process qui est gere par notre API route
      {
        source: '/api/preview',
        destination: `${backendUrl}/api/preview`,
      },
      {
        source: '/api/models',
        destination: `${backendUrl}/api/models`,
      },
      {
        source: '/api/ollama/:path*',
        destination: `${backendUrl}/api/ollama/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
