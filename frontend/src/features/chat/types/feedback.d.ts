interface ChatFeedbackRequest {
  chatHistoryId: string;
  tags: string[];
  detail: string;
}

interface ChatFeedbackResponse {
  messageId: string;
  chatHistoryId?: string;
  hasFeedback?: boolean;
  tags: string[];
  detail: string;
  createdAt: string;
}
