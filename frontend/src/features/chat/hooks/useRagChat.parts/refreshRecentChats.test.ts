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
});
