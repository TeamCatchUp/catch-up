import { describe, expect, it } from 'vitest';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import type { SlackOriginalContentResponse } from '@/features/hybrid-search/types/slackOriginalApi';

import { mergeSlackOriginalPages } from './mergeSlackOriginalPages';

describe('mergeSlackOriginalPages', () => {
  it('returns null when no pages exist', () => {
    expect(mergeSlackOriginalPages([])).toBeNull();
  });

  it('concatenates items and merges user metadata from every page', () => {
    const secondPage = {
      ...slackOriginalThreadResponse,
      items: [
        {
          ...slackOriginalThreadResponse.items[0],
          id: 'second-page-item',
          raw_payload: {
            ...slackOriginalThreadResponse.items[0].raw_payload,
            messages: [
              {
                type: 'message',
                user: 'U_SECOND',
                ts: '1779601400.000000',
                thread_ts: slackOriginalThreadResponse.metadata.thread_ts,
                text: 'second page reply',
              },
            ],
          },
        },
      ],
      metadata: {
        ...slackOriginalThreadResponse.metadata,
        users_by_id: {
          U_SECOND: {
            id: 'U_SECOND',
            name: 'second',
            display_name: 'Second User',
            profile_image_url: 'https://example.com/second.png',
          },
        },
      },
      next_cursor: null,
      fetched_at: '2026-05-31T00:01:00Z',
    } satisfies SlackOriginalContentResponse;

    const merged = mergeSlackOriginalPages([
      { ...slackOriginalThreadResponse, next_cursor: 'cursor-1' },
      secondPage,
    ]);

    expect(merged?.document_id).toBe(slackOriginalThreadResponse.document_id);
    expect(merged?.metadata.channel_id).toBe(slackOriginalThreadResponse.metadata.channel_id);
    expect(merged?.metadata.users_by_id.U_PARENT?.display_name).toBe(
      '작성자명 text text text text text text text text',
    );
    expect(merged?.metadata.users_by_id.U_SECOND?.display_name).toBe('Second User');
    expect(merged?.items).toHaveLength(slackOriginalThreadResponse.items.length + 1);
    expect(merged?.items.at(-1)?.id).toBe('second-page-item');
    expect(merged?.next_cursor).toBeNull();
    expect(merged?.fetched_at).toBe('2026-05-31T00:01:00Z');
  });
});
