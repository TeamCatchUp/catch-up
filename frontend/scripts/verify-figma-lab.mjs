#!/usr/bin/env node

import { readdir, readFile } from 'node:fs/promises';
import { extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const SOURCE_EXTENSIONS = new Set(['.ts', '.tsx']);
const TEST_FILE_PATTERN = /\.(test|spec)\.[cm]?[tj]sx?$/;
const FIGMA_CASE_PATTERN = /\.figma-case\.[cm]?tsx?$/;
const SCALEABLE_ARBITRARY_PATTERN =
  /\b(?<prefix>gap|[mp][trblxy]?|w|h|min-w|max-w|min-h|max-h)-\[(?<value>\d+)px\]/g;

const PRIMITIVE_CLASS_RULES = [
  {
    pattern: /\bbg-white\b/g,
    message: (match) => `avoid primitive class ${match}; use semantic tokens instead.`,
  },
  {
    pattern: /\b(?:text|bg|border)-gray-\d+\b/g,
    message: (match) => `avoid primitive class ${match}; use semantic tokens instead.`,
  },
  {
    pattern: /\b(?:text|bg|border)-blue-\d+\b/g,
    message: (match) => `avoid primitive class ${match}; use semantic tokens instead.`,
  },
  {
    pattern: /\bborder-neutral-\d+\b/g,
    message: (match) => `avoid primitive class ${match}; use semantic tokens instead.`,
  },
  {
    pattern: /\bz-\d+\b/g,
    message: (match) => `avoid numeric z-index class ${match}; use semantic z-index tokens instead.`,
  },
];

export async function collectSourceFiles(rootDir) {
  let entries;
  try {
    entries = await readdir(rootDir, { withFileTypes: true });
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return [];
    }
    throw error;
  }

  const files = [];

  for (const entry of entries) {
    const entryPath = join(rootDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectSourceFiles(entryPath)));
      continue;
    }

    if (!SOURCE_EXTENSIONS.has(extname(entry.name))) {
      continue;
    }
    if (TEST_FILE_PATTERN.test(entry.name)) {
      continue;
    }

    files.push(entryPath);
  }

  return files.sort();
}

export async function collectFigmaCaseFiles(rootDir) {
  let entries;
  try {
    entries = await readdir(rootDir, { withFileTypes: true });
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return [];
    }
    throw error;
  }

  const files = [];

  for (const entry of entries) {
    const entryPath = join(rootDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectFigmaCaseFiles(entryPath)));
      continue;
    }

    if (FIGMA_CASE_PATTERN.test(entry.name)) {
      files.push(entryPath);
    }
  }

  return files.sort();
}

export async function collectVerificationFiles({ featuresRoot, labRoot }) {
  const files = [
    ...(await collectFigmaCaseFiles(featuresRoot)),
    ...(await collectSourceFiles(labRoot)),
  ];

  return [...new Set(files)].sort();
}

export function findFigmaLabViolations(sourceText, fileLabel) {
  const violations = [];

  for (const rule of PRIMITIVE_CLASS_RULES) {
    for (const match of sourceText.matchAll(rule.pattern)) {
      violations.push(`${fileLabel}: ${rule.message(match[0])}`);
    }
  }

  for (const match of sourceText.matchAll(SCALEABLE_ARBITRARY_PATTERN)) {
    const pixelValue = Number(match.groups?.value);
    if (pixelValue > 0 && pixelValue % 4 === 0) {
      violations.push(`${fileLabel}: replace ${match[0]} with the Tailwind scale equivalent.`);
    }
  }

  return violations;
}

export async function verifyFigmaLab(rootDir) {
  const files = await collectSourceFiles(rootDir);
  const violations = [];

  for (const file of files) {
    const sourceText = await readFile(file, 'utf-8');
    violations.push(...findFigmaLabViolations(sourceText, relative(rootDir, file)));
  }

  return violations;
}

export async function verifyFigmaLabTargets({ featuresRoot, labRoot }) {
  const files = await collectVerificationFiles({ featuresRoot, labRoot });
  const violations = [];

  for (const file of files) {
    const sourceText = await readFile(file, 'utf-8');
    violations.push(...findFigmaLabViolations(sourceText, relative(process.cwd(), file)));
  }

  return violations;
}

async function main() {
  const cwd = process.cwd();
  const explicitTarget = process.argv[2];
  const violations = explicitTarget
    ? await verifyFigmaLab(explicitTarget)
    : await verifyFigmaLabTargets({
        featuresRoot: join(cwd, 'src/features'),
        labRoot: join(cwd, 'src/app/(dev)/figma-lab'),
      });

  if (violations.length > 0) {
    console.error(violations.join('\n'));
    process.exitCode = 1;
    return;
  }

  console.log('Figma Lab static verification passed');
}

const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] === currentFile) {
  await main();
}
