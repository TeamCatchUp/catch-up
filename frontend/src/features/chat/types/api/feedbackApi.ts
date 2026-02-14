/**
 * 피드백 제출 요청 API 바디 타입.
 * @interface ChatFeedbackRequestApi
 */
export interface ChatFeedbackRequestApi {
  chat_history_id: string;
  tags: string[];
  detail: string;
}

/**
 * 피드백 제출 응답 API 타입.
 * @interface ChatFeedbackResponseApi
 */
export interface ChatFeedbackResponseApi {
  message_id: string;
  chat_history_id?: string;
  has_feedback?: boolean;
  tags: string[];
  detail: string;
  created_at: string;
}
