import { describe, expect, it } from 'vitest';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';

import { mergeSlackOriginalPages } from './mergeSlackOriginalPages';

describe('mergeSlackOriginalPages', () => {
  it('returns null when no pages exist', () => {
    expect(mergeSlackOriginalPages([])).toBeNull();
  });

  it('concatenates items and keeps metadata from the first page', () => {
    const secondPage = {
      ...slackOriginalThreadResponse,
      items: [
        {
          ...slackOriginalThreadResponse.items[0],
          id: 'second-page-item',
        },
      ],
      next_cursor: null,
      fetched_at: '2026-05-31T00:01:00Z',
    };

    const merged = mergeSlackOriginalPages([
      { ...slackOriginalThreadResponse, next_cursor: 'cursor-1' },
      secondPage,
    ]);

    expect(merged?.document_id).toBe(slackOriginalThreadResponse.document_id);
    expect(merged?.metadata).toBe(slackOriginalThreadResponse.metadata);
    expect(merged?.items).toHaveLength(slackOriginalThreadResponse.items.length + 1);
    expect(merged?.items.at(-1)?.id).toBe('second-page-item');
    expect(merged?.next_cursor).toBeNull();
    expect(merged?.fetched_at).toBe('2026-05-31T00:01:00Z');
  });
});
