/** 페이지네이션 응답 공통 타입 (백엔드 BasePagination[T]) */
export interface PaginatedResponse<T> {
  total: number;
  page: number;
  size: number;
  items: T[];
}

/** 최근 검색 쿼리 API 응답 항목 */
export interface RecentQueryResponse {
  id: number;
  session_id: string;
  content: string;
  created_at: string;
}

/** 채팅 히스토리 API 응답 항목 */
export interface ChatHistoryMessageResponse {
  id: number;
  sender_type: 'human' | 'assistant';
  content: string;
  created_at: string;
  sources?: unknown[];
  chat_history_id?: string | number | null;
  has_feedback?: boolean | null;
}

/** 최근 검색 쿼리 목록 API 응답 */
export type RecentQueriesResponse = PaginatedResponse<RecentQueryResponse>;

/** 채팅방 API 응답 항목 */
export interface ChatroomResponse {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

/** 채팅방 목록 API 응답 */
export type ChatroomsResponse = PaginatedResponse<ChatroomResponse>;

/** 세션 내 쿼리 목록 API 응답 */
export type SessionQueriesResponse = PaginatedResponse<RecentQueryResponse>;

/** 세션 메시지 목록 API 응답 */
export interface SessionMessagesResponse extends PaginatedResponse<ChatHistoryMessageResponse> {
  title: string;
  session_id: string;
}
