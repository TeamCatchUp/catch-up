import reactQuery from '@tanstack/eslint-plugin-query';
import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
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
    // E2E and test artifacts
    'e2e/**',
    'output/**',
    'playwright-report/**',
    'storybook-static/**',
    'test-results/**',
    // Local agent/tooling artifacts
    '.codex/**',
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

      // _ prefix는 의도적으로 사용하지 않는 인자/변수임을 표시 (관습)
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
          destructuredArrayIgnorePattern: '^_',
        },
      ],

      'prettier/prettier': 'off',
    },
  },
  // shared/components/ui 래퍼 사용 강제: Radix·cmdk 직접 import 금지
  {
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@radix-ui/*'],
              message: '@radix-ui 직접 import 금지. @/shared/components/ui 의 래퍼 컴포넌트를 사용하세요.',
            },
            {
              group: ['cmdk'],
              message: 'cmdk 직접 import 금지. @/shared/components/ui/command 를 사용하세요.',
            },
            {
              group: ['@headlessui/*'],
              message: '@headlessui 는 제거되었습니다. shadcn 컴포넌트를 사용하세요.',
            },
          ],
        },
      ],
    },
    ignores: ['src/shared/components/ui/**', 'src/test/**'],
  },
  // 3-Layer 아키텍처 의존성 규칙: app → features → shared
  {
    plugins: {
      boundaries,
    },
    settings: {
      'boundaries/elements': [
        { type: 'app', pattern: ['src/app'], mode: 'folder' },
        { type: 'features', pattern: ['src/features/*'], mode: 'folder' },
        { type: 'shared', pattern: ['src/shared'], mode: 'folder' },
        { type: 'test', pattern: ['src/test'], mode: 'folder' },
      ],
    },
    rules: {
      'boundaries/dependencies': [
        'error',
        {
          default: 'disallow',
          rules: [
            { from: { type: 'app' }, allow: { to: { type: ['features', 'shared'] } } },
            { from: { type: 'features' }, allow: { to: { type: 'shared' } } },
            { from: { type: 'shared' }, allow: { to: { type: 'shared' } } },
            { from: { type: 'test' }, allow: { to: { type: ['shared', 'features', 'test'] } } },
          ],
        },
      ],
    },
  },
  // 코로케이션된 테스트 파일은 boundary 규칙 면제 — MSW server 등 test 인프라 접근 필요.
  {
    files: ['**/*.test.{ts,tsx}'],
    rules: {
      'boundaries/dependencies': 'off',
    },
  },
]);

export default eslintConfig;
