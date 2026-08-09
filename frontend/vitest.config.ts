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
            // Windows 동적 포트 범위(49152~65535) 안의 포트는 Hyper-V/WSL이 부팅마다 100개
            // 단위로 예약해 가서 EACCES로 죽는다 — 예약 목록이 재부팅마다 바뀌므로
            // "지금은 비어 있다"로는 못 고른다. 실제로 63315 → 53315 순으로 두 번 당했다.
            // 동적 범위 밖(<49152)으로 내리면 그 예약 대상에서 아예 빠진다.
            // 확인: netsh int ipv4 show dynamicport tcp / show excludedportrange protocol=tcp
            api: { port: 7331 },
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
