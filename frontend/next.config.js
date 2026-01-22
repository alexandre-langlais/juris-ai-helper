/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',

  // Timeout pour les requetes longues (5 minutes)
  experimental: {
    serverActions: {
      bodySizeLimit: '50mb',
    },
  }
};

module.exports = nextConfig;
