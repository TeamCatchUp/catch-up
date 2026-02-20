import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type {
  ChatroomsResponse,
  RecentQueriesResponse,
  SessionMessagesResponse,
  SessionQueriesResponse,
} from '@/shared/types/query/api';
import { isValidSessionId } from '@/shared/utils/sessionId';

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
