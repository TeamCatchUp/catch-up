import type { MockChatFeedbackResponse } from './types';

export const MOCK_FEEDBACK_RESPONSE: MockChatFeedbackResponse = {
  message_id: 'mock-msg-001',
  chat_history_id: '',
  has_feedback: true,
  tags: [],
  detail: '',
  created_at: new Date().toISOString(),
};
