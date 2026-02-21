/** 관리자용 이용자 질문 로그 아이템 */
export interface QuestionLogItem {
  id: string;
  sessionId: string;
  query: string;
  createdAt: string;
  rawDate: Date;
  fullDate: string;
  relativeDate: string;
  isSaved: boolean;
}
