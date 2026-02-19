import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type {
  ChatroomsResponse,
  RecentQueriesResponse,
  SessionMessagesResponse,
  SessionQueriesResponse,
} from '@/shared/types/query/api';

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
      enabled: !!id,
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
      enabled: !!id && id !== 'new',
    }),
};
