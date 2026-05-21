// 사용자 수동 검색 기록 조회 queryOptions.
// Backend: GET /api/v1/search/queries?period=all
// page/size 파라미터 제거됨 (PR #689) — 최근 20개 고정 응답.

import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type { SearchQueriesResponse } from '@/shared/types/searchHistoryApi';

export const searchHistoryQueries = {
  all: () => ['search', 'queries'] as const,
  list: () =>
    queryOptions({
      queryKey: [...searchHistoryQueries.all(), { period: 'all' }] as const,
      queryFn: async (): Promise<SearchQueriesResponse> => {
        const { data } = await api.get<SearchQueriesResponse>(API.search.queries, {
          params: { period: 'all' },
        });
        return data;
      },
      staleTime: 60_000,
    }),
};
