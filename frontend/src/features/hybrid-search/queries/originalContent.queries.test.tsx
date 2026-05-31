import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider, useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import { server } from '@/test/msw/server';

import { originalContentQueries } from './originalContent.queries';

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('originalContentQueries', () => {
  it('ChannelTalk detail query sends connector and document_id', async () => {
    server.use(
      http.post('/api/v1/search/original', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body).toEqual({
          connector: 'channel_talk',
          document_id: 'channel_talk:user_chat:chat-1',
        });

        return HttpResponse.json({
          connector: 'channel_talk',
          entity_type: 'user_chat',
          document_id: 'channel_talk:user_chat:chat-1',
          title: '상담',
          url: null,
          items: [],
          metadata: {
            channel_id: 'channel-1',
            channel_name: '채널',
            user_chat_id: 'chat-1',
          },
          next_cursor: null,
          fetched_at: '2026-05-31T00:00:00Z',
        });
      }),
    );

    const { result } = renderHook(
      () =>
        useQuery(
          originalContentQueries.channelTalkDetail({
            connector: 'channel_talk',
            entityType: 'user_chat',
            documentId: 'channel_talk:user_chat:chat-1',
          }),
        ),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.connector).toBe('channel_talk');
  });

  it('Slack infinite query sends null cursor on first page and next_cursor on next page', async () => {
    const bodies: Record<string, unknown>[] = [];

    server.use(
      http.post('/api/v1/search/original', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        bodies.push(body);

        if (body.next_cursor === 'cursor-1') {
          return HttpResponse.json({
            ...slackOriginalThreadResponse,
            next_cursor: null,
            fetched_at: '2026-05-31T00:01:00Z',
          });
        }

        return HttpResponse.json({
          ...slackOriginalThreadResponse,
          next_cursor: 'cursor-1',
          fetched_at: '2026-05-31T00:00:00Z',
        });
      }),
    );

    const { result } = renderHook(
      () =>
        useInfiniteQuery(
          originalContentQueries.slackInfinite({
            connector: 'slack',
            entityType: 'message',
            documentId: slackOriginalThreadResponse.document_id,
          }),
        ),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.hasNextPage).toBe(true);

    await result.current.fetchNextPage();

    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));
    expect(bodies).toEqual([
      {
        connector: 'slack',
        document_id: slackOriginalThreadResponse.document_id,
        next_cursor: null,
      },
      {
        connector: 'slack',
        document_id: slackOriginalThreadResponse.document_id,
        next_cursor: 'cursor-1',
      },
    ]);
    expect(result.current.hasNextPage).toBe(false);
  });

  it('Slack infinite query is disabled for non-Slack message sources', () => {
    const options = originalContentQueries.slackInfinite({
      connector: 'github',
      entityType: 'pr',
      documentId: 'github:pr:1',
    });

    expect(options.enabled).toBe(false);
  });
});
