import api from 'src/api/axios';

export const sendChatQuery = async (queryText: string) => {
  const requestBody = {
    query: queryText,
    sessionId: 'c2dbc41b-c58f-4175-a2bc-9ebf7f8085d1',
    indexName: 'CatchUp_BE_develop_code',
  };

  try {
    const response = await api.post('/api/chat', requestBody);
    return response.data;
  } catch (error) {
    console.error('API 요청 중 에러 발생:', error);
    throw error;
  }
};
