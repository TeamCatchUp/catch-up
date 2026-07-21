import { realpathSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { storybookTest } from '@storybook/addon-vitest/vitest-plugin';
import react from '@vitejs/plugin-react';
import { playwright } from '@vitest/browser-playwright';
import svgr from 'vite-plugin-svgr';
import { defineConfig } from 'vitest/config';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = realpathSync.native(__dirname);

export default defineConfig({
  root: rootDir,
  plugins: [
    react(),
    svgr({
      svgrOptions: { dimensions: false },
      include: '**/*.svg',
    }),
  ],
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: 'unit',
          environment: 'jsdom',
          globals: true,
          setupFiles: ['src/test/setup.ts'],
          exclude: ['node_modules', '.next', 'e2e', 'playwright-report', 'test-results', 'dist'],
          css: true,
        },
      },
      {
        extends: true,
        plugins: [
          storybookTest({
            configDir: path.join(__dirname, '.storybook'),
          }),
        ],
        test: {
          name: 'storybook',
          browser: {
            enabled: true,
            provider: playwright({}),
            headless: true,
            instances: [{ browser: 'chromium' }],
          },
        },
      },
    ],
  },
  resolve: {
    alias: [
      { find: '@/public', replacement: path.resolve(rootDir, './public') },
      { find: '@', replacement: path.resolve(rootDir, './src') },
    ],
  },
});
