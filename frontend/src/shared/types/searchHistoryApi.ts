// 사용자별 수동 검색 기록 API 타입 (snake_case, backend matching).
// Backend: GET /api/v1/search/queries

export type SearchQueriesPeriod = 'today' | '7d' | 'all';

export interface ManualSearchHistoryItem {
  id: number;
  query: string;
  created_at: string; // ISO 8601 datetime
}

export interface SearchQueriesRequest {
  page?: number; // default 1
  size?: number; // default 20, max 100
  period?: SearchQueriesPeriod;
}

export interface BasePagination<T> {
  total: number;
  page: number;
  size: number;
  items: T[];
}

export type SearchQueriesResponse = BasePagination<ManualSearchHistoryItem>;
