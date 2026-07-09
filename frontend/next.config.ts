import type { NextConfig } from 'next';

const nextConfig = {
  reactStrictMode: true,

  images: {
    unoptimized: true,
  },

  output: 'standalone',

  experimental: {
    optimizePackageImports: ['recharts', 'date-fns'],
  },

  // Turbopack SVGR 로더 설정
  turbopack: {
    rules: {
      '*.svg': {
        loaders: [
          {
            loader: '@svgr/webpack',
            options: {
              dimensions: false,
            },
          },
        ],
        as: '*.js',
      },
    },
  },

  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!apiUrl || !apiUrl.startsWith('http')) return [];

    return {
      fallback: [
        {
          source: '/api/:path*',
          destination: `${apiUrl}/api/:path*`,
        },
      ],
    };
  },

  // Webpack fallback (--webpack 모드 실행 시 동작)
  webpack(config) {
    const fileLoaderRule = config.module.rules.find(
      (rule: { test?: RegExp }) => rule?.test instanceof RegExp && rule.test.test('.svg'),
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

    if (fileLoaderRule) fileLoaderRule.exclude = /\.svg$/i;

    return config;
  },
} satisfies NextConfig;

export default nextConfig;
