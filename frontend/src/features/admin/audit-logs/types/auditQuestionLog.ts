/** 감사 로그 — 질문 로그 엔트리 */
export interface AuditQuestionLog {
  logId: string;
  userId: number;
  messageId: number;
  name: string;
  picture: string | null;
  query: string;
  executedAt: string;
}
