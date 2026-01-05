import api from 'src/api/axios';

export const sendChatQuery = async (queryText: string) => {
  const requestBody = {
    query: queryText,
    sessionId: '045cea3a-615e-4be1-a401-90945519b0cc',
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
