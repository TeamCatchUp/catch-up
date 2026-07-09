import type { InfiniteData } from '@tanstack/react-query';
import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { ChatroomsResponse, RecentQueriesResponse } from '@/shared/types/query/api';

import { upsertOptimisticRecentChat } from './refreshRecentChats';

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

describe('upsertOptimisticRecentChat', () => {
  it('adds the pending question to recent query and room caches once', () => {
    const queryClient = createQueryClient();
    const recentQueries: RecentQueriesResponse = {
      total: 0,
      page: 1,
      size: 50,
      items: [],
    };
    const recentRooms: ChatroomsResponse = {
      total: 0,
      page: 1,
      size: 50,
      items: [],
    };
    const input = {
      sessionId: 'session-new',
      content: '  first question  ',
      createdAt: '2026-07-09T10:00:00.000Z',
      tempId: -100,
    };

    queryClient.setQueryData(chatQueries.recentQueries().queryKey, recentQueries);
    queryClient.setQueryData(chatQueries.recentRooms().queryKey, recentRooms);

    upsertOptimisticRecentChat(queryClient, input);
    upsertOptimisticRecentChat(queryClient, input);

    const nextQueries = queryClient.getQueryData<RecentQueriesResponse>(chatQueries.recentQueries().queryKey);
    const nextRooms = queryClient.getQueryData<ChatroomsResponse>(chatQueries.recentRooms().queryKey);

    expect(nextQueries?.total).toBe(1);
    expect(nextQueries?.items).toEqual([
      {
        id: -100,
        session_id: 'session-new',
        content: 'first question',
        created_at: '2026-07-09T10:00:00.000Z',
      },
    ]);
    expect(nextRooms?.total).toBe(1);
    expect(nextRooms?.items[0]).toMatchObject({
      session_id: 'session-new',
      title: 'first question',
      updated_at: '2026-07-09T10:00:00.000Z',
    });
  });

  it('moves an existing room to the top without replacing its title', () => {
    const queryClient = createQueryClient();
    const recentRooms: ChatroomsResponse = {
      total: 2,
      page: 1,
      size: 50,
      items: [
        {
          session_id: 'other-session',
          title: 'Other',
          created_at: '2026-07-09T09:00:00.000Z',
          updated_at: '2026-07-09T09:00:00.000Z',
        },
        {
          session_id: 'session-existing',
          title: 'Original title',
          created_at: '2026-07-09T08:00:00.000Z',
          updated_at: '2026-07-09T08:00:00.000Z',
        },
      ],
    };

    queryClient.setQueryData(chatQueries.recentRooms().queryKey, recentRooms);

    upsertOptimisticRecentChat(queryClient, {
      sessionId: 'session-existing',
      content: 'new question in room',
      createdAt: '2026-07-09T11:00:00.000Z',
      tempId: -101,
    });

    const nextRooms = queryClient.getQueryData<ChatroomsResponse>(chatQueries.recentRooms().queryKey);

    expect(nextRooms?.total).toBe(2);
    expect(nextRooms?.items[0]).toMatchObject({
      session_id: 'session-existing',
      title: 'Original title',
      updated_at: '2026-07-09T11:00:00.000Z',
    });
  });

  it('preserves loaded recent query rows across infinite page boundaries', () => {
    const queryClient = createQueryClient();
    const recentQueries: InfiniteData<RecentQueriesResponse> = {
      pageParams: [1, 2],
      pages: [
        {
          total: 3,
          page: 1,
          size: 2,
          items: [
            { id: 1, session_id: 'session-1', content: 'first', created_at: '2026-07-09T09:00:00.000Z' },
            { id: 2, session_id: 'session-2', content: 'second', created_at: '2026-07-09T08:00:00.000Z' },
          ],
        },
        {
          total: 3,
          page: 2,
          size: 2,
          items: [{ id: 3, session_id: 'session-3', content: 'third', created_at: '2026-07-09T07:00:00.000Z' }],
        },
      ],
    };

    queryClient.setQueryData(chatQueries.recentQueriesInfinite().queryKey, recentQueries);

    upsertOptimisticRecentChat(queryClient, {
      sessionId: 'session-new',
      content: 'new question',
      createdAt: '2026-07-09T12:00:00.000Z',
      tempId: -102,
    });

    const nextQueries = queryClient.getQueryData<InfiniteData<RecentQueriesResponse>>(
      chatQueries.recentQueriesInfinite().queryKey,
    );

    expect(nextQueries?.pageParams).toEqual([1, 2]);
    expect(nextQueries?.pages.map((page) => page.total)).toEqual([4, 4]);
    expect(nextQueries?.pages[0].items.map((item) => item.id)).toEqual([-102, 1]);
    expect(nextQueries?.pages[1].items.map((item) => item.id)).toEqual([2, 3]);
  });

  it('moves an existing room across infinite page boundaries without dropping loaded rows', () => {
    const queryClient = createQueryClient();
    const recentRooms: InfiniteData<ChatroomsResponse> = {
      pageParams: [1, 2],
      pages: [
        {
          total: 4,
          page: 1,
          size: 2,
          items: [
            {
              session_id: 'session-a',
              title: 'A',
              created_at: '2026-07-09T09:00:00.000Z',
              updated_at: '2026-07-09T09:00:00.000Z',
            },
            {
              session_id: 'session-b',
              title: 'B',
              created_at: '2026-07-09T08:00:00.000Z',
              updated_at: '2026-07-09T08:00:00.000Z',
            },
          ],
        },
        {
          total: 4,
          page: 2,
          size: 2,
          items: [
            {
              session_id: 'session-existing',
              title: 'Original title',
              created_at: '2026-07-09T07:00:00.000Z',
              updated_at: '2026-07-09T07:00:00.000Z',
            },
            {
              session_id: 'session-c',
              title: 'C',
              created_at: '2026-07-09T06:00:00.000Z',
              updated_at: '2026-07-09T06:00:00.000Z',
            },
          ],
        },
      ],
    };

    queryClient.setQueryData(chatQueries.recentRoomsInfinite().queryKey, recentRooms);

    upsertOptimisticRecentChat(queryClient, {
      sessionId: 'session-existing',
      content: 'new question',
      createdAt: '2026-07-09T12:00:00.000Z',
      tempId: -103,
    });

    const nextRooms = queryClient.getQueryData<InfiniteData<ChatroomsResponse>>(
      chatQueries.recentRoomsInfinite().queryKey,
    );

    expect(nextRooms?.pageParams).toEqual([1, 2]);
    expect(nextRooms?.pages.map((page) => page.total)).toEqual([4, 4]);
    expect(nextRooms?.pages[0].items.map((item) => item.session_id)).toEqual(['session-existing', 'session-a']);
    expect(nextRooms?.pages[0].items[0]).toMatchObject({
      title: 'Original title',
      updated_at: '2026-07-09T12:00:00.000Z',
    });
    expect(nextRooms?.pages[1].items.map((item) => item.session_id)).toEqual(['session-b', 'session-c']);
  });
});
