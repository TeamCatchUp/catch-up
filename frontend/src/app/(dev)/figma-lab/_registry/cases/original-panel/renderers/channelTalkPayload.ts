import type {
  OriginalBlockPayload,
  OriginalButtonPayload,
  OriginalContent,
  OriginalFilePayload,
  OriginalFormPayload,
  OriginalTextPayload,
} from '@/features/hybrid-search/types/originalApi';

export function textPayload(content: OriginalContent): OriginalTextPayload {
  if (content.content_type !== 'text') throw new Error('expected text content');
  return content.payload;
}

export function blockPayload(content: OriginalContent): OriginalBlockPayload {
  if (content.content_type !== 'block') throw new Error('expected block content');
  return content.payload;
}

export function buttonPayload(content: OriginalContent): OriginalButtonPayload {
  if (content.content_type !== 'button') throw new Error('expected button content');
  return content.payload;
}

export function formPayload(content: OriginalContent): OriginalFormPayload {
  if (content.content_type !== 'form') throw new Error('expected form content');
  return content.payload;
}

export function filePayload(content: OriginalContent): OriginalFilePayload {
  if (content.content_type !== 'file') throw new Error('expected file content');
  return content.payload;
}
