/**
 * Mock 피드백 응답 타입.
 * @interface MockChatFeedbackResponse
 */
export interface MockChatFeedbackResponse {
  message_id: string;
  chat_history_id?: string;
  has_feedback?: boolean;
  tags: string[];
  detail: string;
  created_at: string;
}
