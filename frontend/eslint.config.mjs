import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
import reactQuery from '@tanstack/eslint-plugin-query';
import boundaries from 'eslint-plugin-boundaries';
import simpleImportSort from 'eslint-plugin-simple-import-sort';

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
  ]),
  // import 정렬 자동화 플러그인
  {
    plugins: {
      'simple-import-sort': simpleImportSort,
      '@tanstack/query': reactQuery,
    },
    rules: {
      'simple-import-sort/imports': [
        'error',
        {
          groups: [['^\\u0000'], ['^node:'], ['^react', '^@?\\w'], ['^(@|~)/'], ['^\\.'], ['\\.s?css$']],
        },
      ],
      'simple-import-sort/exports': 'error',

      '@tanstack/query/exhaustive-deps': 'warn',
      '@tanstack/query/no-rest-destructuring': 'warn',

      'prettier/prettier': 'off',
    },
  },
  // 3-Layer 아키텍처 의존성 규칙: app → features → shared
  {
    plugins: {
      boundaries,
    },
    settings: {
      'boundaries/elements': [
        { type: 'app', pattern: ['src/app/*'], mode: 'folder' },
        { type: 'features', pattern: ['src/features/*'], mode: 'folder' },
        { type: 'shared', pattern: ['src/shared/*'], mode: 'folder' },
      ],
    },
    rules: {
      'boundaries/element-types': [
        'error',
        {
          default: 'disallow',
          rules: [
            { from: 'app', allow: ['features', 'shared'] },
            { from: 'features', allow: ['shared'] },
            { from: 'shared', allow: ['shared'] },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;
