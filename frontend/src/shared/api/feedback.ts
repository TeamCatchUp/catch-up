import api from '@/shared/api/client';

export const sendFeedbackQuery = async (body: ChatFeedbackRequest): Promise<ChatFeedbackResponse> => {
  const response = await api.post('/api/chat/feedback', body);
  return response.data;
};
