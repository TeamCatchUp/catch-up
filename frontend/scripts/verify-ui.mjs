#!/usr/bin/env node

import { readdir, readFile } from 'node:fs/promises';
import { extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const SOURCE_EXTENSIONS = new Set(['.ts', '.tsx']);
const STORY_FILE_PATTERN = /\.stories\.[cm]?[tj]sx?$/;
const SCALEABLE_ARBITRARY_PATTERN = /\b(?<prefix>gap|[mp][trblxy]?|w|h|min-w|max-w|min-h|max-h)-\[(?<value>\d+)px\]/g;

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

async function collectSourceFiles(rootDir, predicate) {
  let entries;
  try {
    entries = await readdir(rootDir, { withFileTypes: true });
  } catch (error) {
    if (error?.code === 'ENOENT') return [];
    throw error;
  }

  const files = [];
  for (const entry of entries) {
    const entryPath = join(rootDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectSourceFiles(entryPath, predicate)));
      continue;
    }
    if (!SOURCE_EXTENSIONS.has(extname(entry.name))) continue;
    if (!predicate(entryPath, entry.name)) continue;
    files.push(entryPath);
  }
  return files.sort();
}

export async function collectUiVerificationFiles({ storybookRoot, srcRoot }) {
  const files = [
    ...(await collectSourceFiles(storybookRoot, () => true)),
    ...(await collectSourceFiles(srcRoot, (_path, name) => STORY_FILE_PATTERN.test(name))),
  ];

  return [...new Set(files)].sort();
}

export function findUiViolations(sourceText, fileLabel) {
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

export async function verifyUiTargets({ storybookRoot, srcRoot }) {
  const cwd = process.cwd();
  const files = await collectUiVerificationFiles({ storybookRoot, srcRoot });
  const violations = [];

  for (const file of files) {
    const sourceText = await readFile(file, 'utf-8');
    violations.push(...findUiViolations(sourceText, relative(cwd, file)));
  }

  return violations;
}

async function main() {
  const cwd = process.cwd();
  const violations = await verifyUiTargets({
    storybookRoot: join(cwd, '.storybook'),
    srcRoot: join(cwd, 'src'),
  });

  if (violations.length > 0) {
    console.error(violations.join('\n'));
    process.exitCode = 1;
    return;
  }

  console.log('UI static verification passed');
}

const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] === currentFile) {
  await main();
}
