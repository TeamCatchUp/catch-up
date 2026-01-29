interface ChatFeedbackRequest {
  chatHistoryId: string;
  tags: string[];
  detail: string;
}

interface ChatFeedbackResponse {
  feedbackId: string;
  chatHistoryId: string;
  tags: string[];
  detail: string;
  createdAt: string;
}
