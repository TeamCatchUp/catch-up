interface ChatFeedbackRequest {
  chat_history_id: string;
  tags: string[];
  detail: string;
}

interface ChatFeedbackResponse {
  message_id: string;
  chat_history_id?: string;
  has_feedback?: boolean;
  tags: string[];
  detail: string;
  created_at: string;
}
