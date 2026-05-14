// 사용자별 수동 검색 기록 API 타입 (snake_case, backend matching).
// Backend: GET /api/v1/search/queries?period=all
// 응답: ManualSearchHistoryItem[] (최근 20개 고정, langgraph checkpointer에서 조회).

export type SearchQueriesPeriod = 'today' | '7d' | 'all';

export interface ManualSearchHistoryItem {
  id: number;
  query: string;
  created_at: string; // ISO 8601 datetime
}

export interface SearchQueriesRequest {
  period?: SearchQueriesPeriod;
}

export type SearchQueriesResponse = ManualSearchHistoryItem[];
