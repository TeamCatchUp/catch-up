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
