import api from 'src/api/axios';

export const sendChatQuery = async (queryText: string, sessionId: string, repo: string): Promise<ChatResponse> => {
  const requestBody = {
    query: queryText,
    sessionId: sessionId,
    indexName: repo,
  };

  try {
    const response = await api.post('/api/chat', requestBody);
    return response.data;
  } catch (error) {
    console.error('API 요청 중 에러 발생:', error);
    throw error;
  }
};
