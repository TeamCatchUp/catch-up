import { get as getEmoji } from 'node-emoji';

export function resolveSlackStandardEmoji(name: string | undefined): string | null {
  if (!name) return null;

  const emoji = getEmoji(name);
  return emoji ?? null;
}
