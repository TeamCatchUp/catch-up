import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
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
