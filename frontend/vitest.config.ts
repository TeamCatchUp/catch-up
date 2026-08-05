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
            // 기본 포트 63315는 Windows 예약 포트 범위(63313-63412)에 들어 EACCES가 난다
            api: { port: 53315 },
          },
        },
      },
    ],
  },
  resolve: {
    alias: [
      { find: '@/public', replacement: path.resolve(rootDir, './public') },
      { find: '@', replacement: path.resolve(rootDir, './src') },
      // Next가 내부 alias로 해석하는 가상 모듈 — 테스트에서는 빈 모듈로 대체
      { find: 'server-only', replacement: path.resolve(rootDir, './src/test/stubs/server-only.ts') },
    ],
  },
});
