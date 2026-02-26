/** 저장 토글 path params */
export interface ChatSavePathParams {
  sessionId: string;
  messageId: string | number;
}

/** 저장 토글 응답 */
export interface ChatSaveResponseApi {
  status: string;
  message_id: number;
}
