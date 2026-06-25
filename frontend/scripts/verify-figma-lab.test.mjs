import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  collectFigmaCaseFiles,
  collectSourceFiles,
  collectVerificationFiles,
  findFigmaLabViolations,
} from './verify-figma-lab.mjs';

describe('verify-figma-lab', () => {
  it('allows semantic tokens and non-scale arbitrary values', () => {
    const violations = findFigmaLabViolations(
      'className="bg-fill-normal text-content-normal border-edge-neutral gap-4 w-[3px]"',
      'Component.tsx',
    );

    expect(violations).toEqual([]);
  });

  it('rejects primitive color and numeric z-index classes', () => {
    const violations = findFigmaLabViolations(
      'className="bg-white text-gray-500 border-gray-200 text-blue-500 bg-blue-100 z-50"',
      'Component.tsx',
    );

    expect(violations).toEqual([
      'Component.tsx: avoid primitive class bg-white; use semantic tokens instead.',
      'Component.tsx: avoid primitive class text-gray-500; use semantic tokens instead.',
      'Component.tsx: avoid primitive class border-gray-200; use semantic tokens instead.',
      'Component.tsx: avoid primitive class text-blue-500; use semantic tokens instead.',
      'Component.tsx: avoid primitive class bg-blue-100; use semantic tokens instead.',
      'Component.tsx: avoid numeric z-index class z-50; use semantic z-index tokens instead.',
    ]);
  });

  it('rejects arbitrary pixel spacing when Tailwind scale can represent it', () => {
    const violations = findFigmaLabViolations(
      'className="gap-[16px] px-[20px] w-[18px]"',
      'Component.tsx',
    );

    expect(violations).toEqual([
      'Component.tsx: replace gap-[16px] with the Tailwind scale equivalent.',
      'Component.tsx: replace px-[20px] with the Tailwind scale equivalent.',
    ]);
  });

  it('collects source files while skipping tests', async () => {
    const root = await mkdtemp(join(tmpdir(), 'figma-lab-verify-'));
    try {
      await writeFile(join(root, 'Component.tsx'), '');
      await writeFile(join(root, 'Component.test.tsx'), '');
      await writeFile(join(root, 'notes.md'), '');

      await expect(collectSourceFiles(root)).resolves.toEqual([join(root, 'Component.tsx')]);
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it('collects feature-local figma case files', async () => {
    const root = await mkdtemp(join(tmpdir(), 'figma-lab-cases-'));
    try {
      await writeFile(join(root, 'UsersTable.figma-case.tsx'), '');
      await writeFile(join(root, 'UsersTable.fixture.ts'), '');
      await writeFile(join(root, 'UsersTable.tsx'), '');

      await expect(collectFigmaCaseFiles(root)).resolves.toEqual([
        join(root, 'UsersTable.figma-case.tsx'),
      ]);
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it('combines lab route files with feature-local figma cases', async () => {
    const root = await mkdtemp(join(tmpdir(), 'figma-lab-combined-'));
    const labRoot = join(root, 'lab');
    const featuresRoot = join(root, 'features');
    try {
      await mkdir(labRoot);
      await mkdir(featuresRoot);
      await writeFile(join(labRoot, 'FigmaLabRenderer.tsx'), '');
      await writeFile(join(featuresRoot, 'UsersTable.figma-case.tsx'), '');
      await writeFile(join(featuresRoot, 'UsersTable.tsx'), '');

      await expect(collectVerificationFiles({ featuresRoot, labRoot })).resolves.toEqual([
        join(featuresRoot, 'UsersTable.figma-case.tsx'),
        join(labRoot, 'FigmaLabRenderer.tsx'),
      ]);
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });
});
