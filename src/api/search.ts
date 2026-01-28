import api from '@/api/axios';

export const searchService = {
  getRecentQueries: async () => {
    const res = await api.get('/api/chatrooms/queries');
    return res.data;
  },

  getRecentJiraTickets: async () => {
    const res = await api.get('/api/jira/issues');
    return res.data;
  },

  getRecentChatromms: async () => {
    const res = await api.get('/api/chatrooms');
    return res.data;
  },
};

export const nowChatroomService = {
  getAllQueries: async (sessionId: string) => {
    const res = await api.get(`/api/chatrooms/${sessionId}/queries`);
    return res.data;
  },
};
