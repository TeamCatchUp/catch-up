/** 관리자용 이용자 질문 로그 아이템 (UI 모델) */
export interface QuestionLogItem {
  id: string;
  sessionId: string;
  query: string;
  createdAt: string;
  rawDate: Date;
  fullDate: string;
  relativeDate: string;
  isSaved: boolean;
  answerId: number | null;
}

/** GET /api/v1/admin/queries 쿼리 파라미터 */
export interface AdminQueryParams {
  page: number;
  size: number;
  search?: string;
  target_user_id?: number;
  is_saved?: boolean;
  period?: 'today' | '7d' | '30d' | 'all';
  sort?: 'asc' | 'desc';
}
