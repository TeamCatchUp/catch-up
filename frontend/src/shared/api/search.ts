import api from '@/shared/api/client';
import type {
  RecentQueriesResponse,
  JiraTicketResponse,
  ChatroomsResponse,
  SessionQueriesResponse,
} from '@/features/search/types/api';

export const searchService = {
  getRecentQueries: async (): Promise<RecentQueriesResponse> => {
    const res = await api.get<RecentQueriesResponse>('/api/chatrooms/queries');
    return res.data;
  },

  getRecentJiraTickets: async (): Promise<JiraTicketResponse[]> => {
    const res = await api.get<JiraTicketResponse[]>('/api/jira/issues');
    return res.data;
  },

  getRecentChatrooms: async (): Promise<ChatroomsResponse> => {
    const res = await api.get<ChatroomsResponse>('/api/chatrooms');
    return res.data;
  },
};

export const nowChatroomService = {
  getAllQueries: async (sessionId: string): Promise<SessionQueriesResponse> => {
    const res = await api.get<SessionQueriesResponse>(`/api/chatrooms/${sessionId}/queries`);
    return res.data;
  },
};
