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
        // PNG를 next-image 변환에서 빼면 vite 기본 자산 처리로 URL 문자열이 된다.
        // 그대로면 next/image가 width를 요구해 터지므로, NextImageStub alias와 반드시 짝으로 쓴다.
        excludeFiles: ['**/*.svg', '**/*.png'],
      },
    },
  },
  stories: ['../src/**/*.mdx', '../src/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
  addons: ['@storybook/addon-docs', '@storybook/addon-vitest'],
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
          // virtual:next-image가 Windows 절대 경로의 백슬래시를 이스케이프하지 않아
          // PNG static import를 하는 컴포넌트를 띄울 수 없다. Storybook에서만 <img>로 대체한다.
          { find: /^next\/image$/, replacement: path.resolve(__dirname, './NextImageStub.tsx') },
          { find: '@/public', replacement: path.resolve(rootDir, './public') },
          { find: '@', replacement: path.resolve(rootDir, './src') },
        ],
      },
    });
  },
};

export default config;
