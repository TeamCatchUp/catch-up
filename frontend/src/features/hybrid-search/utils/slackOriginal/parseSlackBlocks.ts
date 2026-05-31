import type {
  SlackBlockRaw,
  SlackRichTextBlockElementRaw,
  SlackRichTextElementRaw,
  SlackRichTextListRaw,
  SlackRichTextPreformattedRaw,
  SlackRichTextQuoteRaw,
  SlackRichTextSectionRaw,
  SlackTextStyleRaw,
  SlackUserMetadata,
} from '@/features/hybrid-search/types/slackOriginalApi';
import type { SlackBlockView, SlackRichTextToken } from '@/features/hybrid-search/types/slackOriginalModel';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

import { parseSlackTextFallback, parseSlackTextTokens } from './parseSlackTextFallback';

function isSection(element: SlackRichTextBlockElementRaw): element is SlackRichTextSectionRaw {
  return element.type === 'rich_text_section';
}

function isList(element: SlackRichTextBlockElementRaw): element is SlackRichTextListRaw {
  return element.type === 'rich_text_list';
}

function isQuote(element: SlackRichTextBlockElementRaw): element is SlackRichTextQuoteRaw {
  return element.type === 'rich_text_quote';
}

function isPreformatted(element: SlackRichTextBlockElementRaw): element is SlackRichTextPreformattedRaw {
  return element.type === 'rich_text_preformatted';
}

function resolveUserLabel(userId: string | undefined, usersById: Record<string, SlackUserMetadata>): string {
  if (!userId) return '@unknown';
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

function textToTokens(text: string | undefined, style?: SlackTextStyleRaw): SlackRichTextToken[] {
  if (!text) return [];
  return parseSlackTextTokens(text, {}, normalizeStyle(style));
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function styleValue(value: unknown): SlackTextStyleRaw | undefined {
  if (!value || typeof value !== 'object') return undefined;

  const raw = value as Record<string, unknown>;
  return normalizeStyle({
    bold: raw.bold === true,
    italic: raw.italic === true,
    strike: raw.strike === true,
    code: raw.code === true,
    underline: raw.underline === true,
  });
}

function elementToTokens(
  element: SlackRichTextElementRaw,
  usersById: Record<string, SlackUserMetadata>,
): SlackRichTextToken[] {
  switch (element.type) {
    case 'text':
      return textToTokens(stringValue(element.text), styleValue(element.style));
    case 'link': {
      const url = stringValue(element.url);
      const text = stringValue(element.text) || url || '';
      const style = styleValue(element.style);
      if (!url || !isSafeUrl(url)) return textToTokens(text, style);
      return [{ type: 'link', href: url, text, style }];
    }
    case 'user':
      return [
        {
          type: 'mention',
          label: resolveUserLabel(stringValue(element.user_id), usersById),
          style: styleValue(element.style),
        },
      ];
    case 'channel':
      return [
        {
          type: 'mention',
          label: stringValue(element.channel_id) ? `#${stringValue(element.channel_id)}` : '#unknown',
          style: styleValue(element.style),
        },
      ];
    case 'usergroup':
      return [
        {
          type: 'mention',
          label: stringValue(element.usergroup_id) ? `@${stringValue(element.usergroup_id)}` : '@usergroup',
          style: styleValue(element.style),
        },
      ];
    case 'emoji':
      return [
        {
          type: 'emoji',
          label:
            stringValue(element.unicode) || (stringValue(element.name) ? `:${stringValue(element.name)}:` : ':emoji:'),
        },
      ];
    case 'date':
      return textToTokens(stringValue(element.fallback) || '', undefined);
    case 'broadcast':
      return [{ type: 'mention', label: stringValue(element.range) ? `@${stringValue(element.range)}` : '@channel' }];
    default:
      return [];
  }
}

function richElementsToTokens(
  elements: SlackRichTextElementRaw[] | undefined,
  usersById: Record<string, SlackUserMetadata>,
): SlackRichTextToken[] {
  return (elements ?? []).flatMap((element) => elementToTokens(element, usersById));
}

function richElementsToPlainText(
  elements: SlackRichTextElementRaw[] | undefined,
  usersById: Record<string, SlackUserMetadata>,
): string {
  return richElementsToTokens(elements, usersById)
    .map((token) => {
      if (token.type === 'line_break') return '\n';
      if (token.type === 'text') return token.text;
      if (token.type === 'mention') return token.label;
      if (token.type === 'link') return token.text;
      if (token.type === 'emoji') return token.label;
      return '';
    })
    .join('');
}

function blockTextToViews(block: SlackBlockRaw, usersById: Record<string, SlackUserMetadata>): SlackBlockView[] {
  const views: SlackBlockView[] = [];
  if (block.text?.text) views.push(...parseSlackTextFallback(block.text.text, usersById));

  for (const field of block.fields ?? []) {
    if (field.text) views.push(...parseSlackTextFallback(field.text, usersById));
  }

  return views;
}

function richElementToView(
  element: SlackRichTextBlockElementRaw,
  usersById: Record<string, SlackUserMetadata>,
): SlackBlockView[] {
  if (isSection(element)) {
    const tokens = richElementsToTokens(element.elements, usersById);
    return tokens.length > 0 ? [{ type: 'paragraph', tokens }] : [];
  }

  if (isList(element)) {
    const items = (element.elements ?? [])
      .map((section) => richElementsToTokens(section.elements, usersById))
      .filter((tokens) => tokens.length > 0);

    if (items.length === 0) return [];
    if (element.style === 'ordered') {
      return [{ type: 'ordered_list', items, start: element.offset ?? 1 }];
    }
    return [{ type: 'bullet_list', items }];
  }

  if (isQuote(element)) {
    const tokens = richElementsToTokens(element.elements, usersById);
    return tokens.length > 0 ? [{ type: 'quote', tokens }] : [];
  }

  if (isPreformatted(element)) {
    const text = richElementsToPlainText(element.elements, usersById);
    return text ? [{ type: 'code_block', text }] : [];
  }

  return [];
}

export function parseSlackBlocks(
  blocks: SlackBlockRaw[] | undefined,
  usersById: Record<string, SlackUserMetadata>,
): SlackBlockView[] {
  const views: SlackBlockView[] = [];

  for (const block of blocks ?? []) {
    if (block.type === 'rich_text') {
      for (const element of block.elements ?? []) {
        views.push(...richElementToView(element, usersById));
      }
      continue;
    }

    views.push(...blockTextToViews(block, usersById));
  }

  return views;
}
