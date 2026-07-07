import path from 'node:path';
import { fileURLToPath } from 'node:url';

import type { StorybookConfig } from '@storybook/nextjs-vite';
import { mergeConfig } from 'vite';
import svgr from 'vite-plugin-svgr';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..');

const config: StorybookConfig = {
  framework: {
    name: '@storybook/nextjs-vite',
    options: {
      image: {
        excludeFiles: ['**/*.svg'],
      },
    },
  },
  stories: ['../src/**/*.mdx', '../src/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
  addons: ['@storybook/addon-docs'],
  staticDirs: ['../public'],
  async viteFinal(config) {
    return mergeConfig(config, {
      plugins: [
        svgr({
          svgrOptions: { dimensions: false },
          include: '**/*.svg',
        }),
      ],
      resolve: {
        alias: [
          { find: '@/public', replacement: path.resolve(rootDir, './public') },
          { find: '@', replacement: path.resolve(rootDir, './src') },
        ],
      },
    });
  },
};

export default config;
