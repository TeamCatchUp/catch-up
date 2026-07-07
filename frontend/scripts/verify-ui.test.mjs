import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { collectUiVerificationFiles, findUiViolations, verifyUiTargets } from './verify-ui.mjs';

function normalizePath(path) {
  return path.replaceAll('\\', '/');
}

describe('verify-ui', () => {
  it('rejects primitive color and numeric z-index classes', () => {
    expect(findUiViolations('<div className="bg-white text-gray-500 z-10" />', 'Example.stories.tsx')).toEqual([
      'Example.stories.tsx: avoid primitive class bg-white; use semantic tokens instead.',
      'Example.stories.tsx: avoid primitive class text-gray-500; use semantic tokens instead.',
      'Example.stories.tsx: avoid numeric z-index class z-10; use semantic z-index tokens instead.',
    ]);
  });

  it('rejects scalable arbitrary pixel spacing and sizing', () => {
    expect(findUiViolations('<div className="gap-[20px] w-[40px] h-[37px]" />', 'Example.stories.tsx')).toEqual([
      'Example.stories.tsx: replace gap-[20px] with the Tailwind scale equivalent.',
      'Example.stories.tsx: replace w-[40px] with the Tailwind scale equivalent.',
    ]);
  });

  it('collects storybook config and story files only', async () => {
    const root = await mkdtemp(join(tmpdir(), 'verify-ui-'));
    try {
      const storybookRoot = join(root, '.storybook');
      const srcRoot = join(root, 'src');
      await mkdir(storybookRoot, { recursive: true });
      await mkdir(join(srcRoot, 'feature'), { recursive: true });

      await writeFile(join(storybookRoot, 'preview.tsx'), '');
      await writeFile(join(srcRoot, 'feature', 'Button.stories.tsx'), '');
      await writeFile(join(srcRoot, 'feature', 'Button.tsx'), 'bg-white');
      await writeFile(join(srcRoot, 'feature', 'Button.test.tsx'), 'bg-white');

      expect((await collectUiVerificationFiles({ storybookRoot, srcRoot })).map(normalizePath)).toEqual([
        normalizePath(join(storybookRoot, 'preview.tsx')),
        normalizePath(join(srcRoot, 'feature', 'Button.stories.tsx')),
      ]);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  it('verifies only scoped files', async () => {
    const root = await mkdtemp(join(tmpdir(), 'verify-ui-targets-'));
    try {
      const storybookRoot = join(root, '.storybook');
      const srcRoot = join(root, 'src');
      await mkdir(storybookRoot, { recursive: true });
      await mkdir(srcRoot, { recursive: true });

      await writeFile(join(storybookRoot, 'main.ts'), 'const ok = "bg-fill-normal-normal";');
      await writeFile(join(srcRoot, 'Example.stories.tsx'), '<div className="z-10" />');
      await writeFile(join(srcRoot, 'Production.tsx'), '<div className="bg-white" />');

      const violations = await verifyUiTargets({ storybookRoot, srcRoot });

      expect(violations).toHaveLength(1);
      expect(violations[0]).toContain('Example.stories.tsx');
      expect(violations[0]).toContain('avoid numeric z-index class z-10');
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
});
