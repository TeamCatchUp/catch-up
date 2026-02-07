export interface ChatFeedbackRequest {
  chatHistoryId: string;
  tags: string[];
  detail: string;
}

export interface ChatFeedbackResponse {
  messageId: string;
  chatHistoryId: string;
  hasFeedback: boolean;
  tags: string[];
  detail: string;
  createdAt: string;
}

export const MOCK_FEEDBACK_RESPONSE: ChatFeedbackResponse = {
  messageId: 'mock-msg-001',
  chatHistoryId: '',
  hasFeedback: true,
  tags: [],
  detail: '',
  createdAt: new Date().toISOString(),
};
