import type { NextConfig } from 'next';
import path from 'path';

const nextConfig = {
  reactStrictMode: true,

  images: {
    unoptimized: true,
  },

  output: 'standalone',

  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!apiUrl || !apiUrl.startsWith('http')) return [];

    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },

  webpack(config) {
    const fileLoaderRule = config.module.rules.find(
      (rule: any) => rule?.test instanceof RegExp && rule.test.test('.svg'),
    );

    config.module.rules.push({
      test: /\.svg$/i,
      issuer: fileLoaderRule.issuer,
      use: [
        {
          loader: '@svgr/webpack',
          options: {
            dimensions: false,
          },
        },
      ],
    });

    // fileLoaderRule.exclude = /\.svg$/i;
    if (fileLoaderRule) fileLoaderRule.exclude = /\.svg$/i;

    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      '@': path.resolve(__dirname, 'src'),
    };

    return config;
  },
} satisfies NextConfig;

export default nextConfig;
