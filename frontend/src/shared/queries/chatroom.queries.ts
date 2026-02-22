import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type {
  ChatroomsResponse,
  RecentQueriesResponse,
  RecentQueriesWithSaveStatusResponse,
  SessionMessagesResponse,
  SessionQueriesResponse,
} from '@/shared/types/query/api';
import { isValidSessionId } from '@/shared/utils/sessionId';

const HISTORY_PAGE_SIZE = 50;

export const chatQueries = {
  all: () => ['chatrooms'] as const,
  lists: () => [...chatQueries.all(), 'list'] as const,
  sessions: () => [...chatQueries.all(), 'session'] as const,
  messages: () => [...chatQueries.all(), 'messages'] as const,

  recentRooms: () =>
    queryOptions({
      queryKey: [...chatQueries.lists(), 'recent'] as const,
      queryFn: async (): Promise<ChatroomsResponse> => {
        const res = await api.get<ChatroomsResponse>(API.chatrooms.list);
        return res.data;
      },
    }),

  recentQueries: () =>
    queryOptions({
      queryKey: [...chatQueries.lists(), 'queries'] as const,
      queryFn: async (): Promise<RecentQueriesResponse> => {
        const res = await api.get<RecentQueriesResponse>(API.chatrooms.queries);
        return res.data;
      },
    }),

  recentQueriesWithSaveStatus: () =>
    queryOptions({
      queryKey: [...chatQueries.lists(), 'queries', 'saved-status'] as const,
      queryFn: async (): Promise<RecentQueriesWithSaveStatusResponse> => {
        const res = await api.get<RecentQueriesWithSaveStatusResponse>(API.chatrooms.queriesWithSaveStatus);
        return res.data;
      },
    }),

  /** 무한 스크롤용 질문 히스토리 + 저장 여부 */
  recentQueriesWithSaveStatusInfinite: () =>
    infiniteQueryOptions({
      queryKey: [...chatQueries.lists(), 'queries', 'saved-status', 'infinite'] as const,
      queryFn: async ({ pageParam }): Promise<RecentQueriesWithSaveStatusResponse> => {
        const res = await api.get<RecentQueriesWithSaveStatusResponse>(API.chatrooms.queriesWithSaveStatus, {
          params: { page: pageParam, size: HISTORY_PAGE_SIZE },
        });
        return res.data;
      },
      initialPageParam: 1,
      getNextPageParam: (lastPage, allPages) => {
        const totalPages = Math.ceil(lastPage.total / HISTORY_PAGE_SIZE);
        return allPages.length < totalPages ? allPages.length + 1 : undefined;
      },
    }),

  sessionQueries: (id: string) =>
    queryOptions({
      queryKey: [...chatQueries.sessions(), id] as const,
      queryFn: async (): Promise<SessionQueriesResponse> => {
        const res = await api.get<SessionQueriesResponse>(API.chatrooms.session(id));
        return res.data;
      },
      // placeholder(/chat/new)나 잘못된 ID에서는 /rooms/{id} 호출 자체를 막음
      enabled: isValidSessionId(id),
    }),

  sessionMessages: (id: string, page = 1, size = 50) =>
    queryOptions({
      queryKey: [...chatQueries.messages(), id, page, size] as const,
      queryFn: async (): Promise<SessionMessagesResponse> => {
        const res = await api.get<SessionMessagesResponse>(API.chatrooms.messages(id), {
          params: { page, size },
        });
        return res.data;
      },
      // 세션 확정 전에는 메시지 API를 호출하지 않음
      enabled: isValidSessionId(id),
    }),
};
