/** Mock 피드백 응답 타입 (백엔드 PATCH feedback 응답과 동일) */
export interface MockChatFeedbackResponse {
  status: string;
  message_id: number;
  is_liked: boolean | null;
}
