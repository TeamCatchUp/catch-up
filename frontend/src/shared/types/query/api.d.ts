/** 최근 검색 쿼리 API 응답 */
export interface RecentQueryResponse {
  query: string;
  sessionId: string;
  createdAt: string;
}

/** 최근 검색 쿼리 목록 API 응답 */
export interface RecentQueriesResponse {
  content: RecentQueryResponse[];
}

/** Jira 티켓 API 응답 */
export interface JiraTicketResponse {
  issueKey: string;
  summary: string;
}

/** 채팅방 API 응답 */
export interface ChatroomResponse {
  sessionId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

/** 채팅방 목록 API 응답 */
export interface ChatroomsResponse {
  content: ChatroomResponse[];
}

/** 세션 내 쿼리 목록 API 응답 */
export interface SessionQueriesResponse {
  content: RecentQueryResponse[];
}
