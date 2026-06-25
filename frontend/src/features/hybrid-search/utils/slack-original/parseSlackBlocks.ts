import type {
  SlackBlockRaw,
  SlackRichTextBlockElementRaw,
  SlackRichTextListRaw,
  SlackRichTextPreformattedRaw,
  SlackRichTextQuoteRaw,
  SlackRichTextSectionRaw,
  SlackUserMetadata,
} from '@/features/hybrid-search/types/slackOriginalApi';
import type { SlackBlockView } from '@/features/hybrid-search/types/slackOriginalModel';

import { richElementsToPlainText, richElementsToTokens } from './parseSlackRichTextTokens';
import { parseSlackTextFallback } from './parseSlackTextFallback';

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
