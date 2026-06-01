import type { SlackTextStyleRaw, SlackUserMetadata } from '@/features/hybrid-search/types/slackOriginalApi';
import type { SlackBlockView, SlackRichTextToken } from '@/features/hybrid-search/types/slackOriginalModel';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

import { resolveSlackStandardEmoji } from './slackStandardEmoji';

const INLINE_TOKEN_PATTERN = /(`[^`\n]+`|\*[^*\n]+\*|:[A-Za-z0-9_+-]+:|_[^_\n]+_|~[^~\n]+~|<[^>\n]+>|\n)/g;

function decodeSlackTextEntities(text: string): string {
  return text.replace(/&(amp|lt|gt);/g, (entity) => {
    if (entity === '&amp;') return '&';
    if (entity === '&lt;') return '<';
    return '>';
  });
}

function resolveUserLabel(userId: string, usersById: Record<string, SlackUserMetadata>): string {
  const user = usersById[userId];
  const name = user?.display_name || user?.name || userId;
  return `@${name}`;
}

function normalizeStyle(style: SlackTextStyleRaw | undefined): SlackTextStyleRaw | undefined {
  if (!style) return undefined;

  const normalized: SlackTextStyleRaw = {};
  if (style.bold) normalized.bold = true;
  if (style.italic) normalized.italic = true;
  if (style.strike) normalized.strike = true;
  if (style.code) normalized.code = true;
  if (style.underline) normalized.underline = true;

  return Object.keys(normalized).length > 0 ? normalized : undefined;
}

function textToken(text: string, style?: SlackTextStyleRaw): SlackRichTextToken[] {
  if (!text) return [];
  return [{ type: 'text', text: decodeSlackTextEntities(text), style: normalizeStyle(style) }];
}

function parseSlackSpecialToken(
  token: string,
  usersById: Record<string, SlackUserMetadata>,
  style?: SlackTextStyleRaw,
): SlackRichTextToken[] {
  const inner = token.slice(1, -1);

  if (inner.startsWith('@')) {
    return [{ type: 'mention', label: resolveUserLabel(inner.slice(1), usersById), style: normalizeStyle(style) }];
  }

  if (inner.startsWith('#')) {
    const [, label] = inner.split('|');
    return [
      {
        type: 'mention',
        label: label ? `#${decodeSlackTextEntities(label)}` : `#${inner.slice(1)}`,
        style: normalizeStyle(style),
      },
    ];
  }

  if (inner.startsWith('!')) {
    const label = inner.split('^')[0]?.slice(1) || 'channel';
    return [{ type: 'mention', label: `@${label}`, style: normalizeStyle(style) }];
  }

  const [rawUrl, rawLabel] = inner.split('|');
  const url = decodeSlackTextEntities(rawUrl ?? '');
  const label = rawLabel ? decodeSlackTextEntities(rawLabel) : undefined;
  if (isSafeUrl(url)) {
    return [{ type: 'link', href: url, text: label || url, style: normalizeStyle(style) }];
  }

  return textToken(label || inner, style);
}

function parseInlineText(
  text: string,
  usersById: Record<string, SlackUserMetadata>,
  style?: SlackTextStyleRaw,
): SlackRichTextToken[] {
  const tokens: SlackRichTextToken[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(INLINE_TOKEN_PATTERN)) {
    const raw = match[0];
    const index = match.index ?? 0;

    tokens.push(...textToken(text.slice(lastIndex, index), style));

    if (raw === '\n') {
      tokens.push({ type: 'line_break' });
    } else if (raw.startsWith('<') && raw.endsWith('>')) {
      tokens.push(...parseSlackSpecialToken(raw, usersById, style));
    } else if (raw.startsWith('`') && raw.endsWith('`')) {
      tokens.push(...textToken(raw.slice(1, -1), { ...style, code: true }));
    } else if (raw.startsWith('*') && raw.endsWith('*')) {
      tokens.push(...parseInlineText(raw.slice(1, -1), usersById, { ...style, bold: true }));
    } else if (raw.startsWith(':') && raw.endsWith(':')) {
      tokens.push({ type: 'emoji', label: resolveSlackStandardEmoji(raw.slice(1, -1)) ?? raw });
    } else if (raw.startsWith('_') && raw.endsWith('_')) {
      tokens.push(...parseInlineText(raw.slice(1, -1), usersById, { ...style, italic: true }));
    } else if (raw.startsWith('~') && raw.endsWith('~')) {
      tokens.push(...parseInlineText(raw.slice(1, -1), usersById, { ...style, strike: true }));
    }

    lastIndex = index + raw.length;
  }

  tokens.push(...textToken(text.slice(lastIndex), style));
  return tokens;
}

export function parseSlackTextTokens(
  text: string,
  usersById: Record<string, SlackUserMetadata>,
  style?: SlackTextStyleRaw,
): SlackRichTextToken[] {
  return parseInlineText(text, usersById, style);
}

export function parseSlackTextFallback(text: string, usersById: Record<string, SlackUserMetadata>): SlackBlockView[] {
  const tokens = parseSlackTextTokens(text, usersById);
  return tokens.length > 0 ? [{ type: 'paragraph', tokens }] : [];
}
