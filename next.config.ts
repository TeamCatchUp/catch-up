import type { NextConfig } from 'next';
import path from 'path';

const nextConfig = {
  reactStrictMode: true,

  images: {
    unoptimized: true,
  },
  experimental: {
    // @ts-expect-error Next 16 turbo option
    turbo: false,
  },

  webpack(config) {
    const fileLoaderRule = config.module.rules.find(
      (rule: any) => rule?.test instanceof RegExp && rule.test.test('.svg'),
    );

    config.module.rules.push({
      test: /\.svg$/i,
      issuer: fileLoaderRule.issuer,
      use: ['@svgr/webpack'],
    });

    fileLoaderRule.exclude = /\.svg$/i;

    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      '@': path.resolve(__dirname, 'src'),
    };

    return config;
  },
} satisfies NextConfig;

export default nextConfig;
