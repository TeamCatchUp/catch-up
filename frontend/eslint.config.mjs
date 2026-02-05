import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
import simpleImportSort from 'eslint-plugin-simple-import-sort';
import reactQuery from '@tanstack/eslint-plugin-query';

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
      '@tanstack/query/no-useless-promise': 'warn',

      'prettier/prettier': 'off',
    },
  },
]);

export default eslintConfig;
