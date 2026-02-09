/** 최근 검색 쿼리 API 응답 */
export interface RecentQueryResponse {
  query: string;
  session_id: string;
  created_at: string;
}

/** 최근 검색 쿼리 목록 API 응답 */
export interface RecentQueriesResponse {
  content: RecentQueryResponse[];
}

/** Jira 티켓 API 응답 */
export interface JiraTicketResponse {
  issue_key: string;
  summary: string;
}

/** 채팅방 API 응답 */
export interface ChatroomResponse {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

/** 채팅방 목록 API 응답 */
export interface ChatroomsResponse {
  content: ChatroomResponse[];
}

/** 세션 내 쿼리 목록 API 응답 */
export interface SessionQueriesResponse {
  content: RecentQueryResponse[];
}
