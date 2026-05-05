import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import svgr from 'vite-plugin-svgr';
import { defineConfig } from 'vitest/config';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    svgr({
      svgrOptions: { dimensions: false },
      include: '**/*.svg',
    }),
  ],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['node_modules', '.next', 'e2e', 'playwright-report', 'test-results', 'dist'],
    css: true,
  },
  resolve: {
    alias: [
      { find: '@/public', replacement: path.resolve(__dirname, './public') },
      { find: '@', replacement: path.resolve(__dirname, './src') },
    ],
  },
});
