import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { HybridSearchResponse, ToolFilter } from '../types/hybridSearchApi';

export const HYBRID_SEARCH_PAGE_SIZE = 7;

interface ListParams {
  keyword: string;
  tools: ToolFilter[];
  page: number;
}

// axios 기본 직렬화는 버전/설정에 따라 ?key[]=v 또는 ?key=v1&key=v2로 갈림.
// FastAPI는 List 파라미터에 repeat 포맷(?key=v1&key=v2)을 기본 기대 → 명시적으로 처리.
function serializeListParams(params: Record<string, unknown>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const v of value) usp.append(key, String(v));
    } else {
      usp.append(key, String(value));
    }
  }
  return usp.toString();
}

export const hybridSearchQueries = {
  all: () => ['search', 'hybrid'] as const,

  // 결과 리스트 — tools/page 변경에 반응.
  list: (params: ListParams) =>
    queryOptions({
      queryKey: [...hybridSearchQueries.all(), 'list', params] as const,
      queryFn: async (): Promise<HybridSearchResponse> => {
        const { data } = await api.get<HybridSearchResponse>(API.search.hybrid, {
          params: {
            keyword: params.keyword,
            limit: HYBRID_SEARCH_PAGE_SIZE,
            offset: (params.page - 1) * HYBRID_SEARCH_PAGE_SIZE,
            tool_filters: params.tools.length > 0 ? params.tools : undefined,
          },
          paramsSerializer: serializeListParams,
        });
        return data;
      },
      enabled: params.keyword.trim().length > 0,
      staleTime: 30_000,
    }),

  // AccentTabs용 source_distribution — keyword에만 의존(tools 무관).
  // 첫 검색 시 1회 fetch, 탭 클릭·페이지 이동에는 cache hit.
  distribution: (keyword: string) =>
    queryOptions({
      queryKey: [...hybridSearchQueries.all(), 'distribution', keyword] as const,
      queryFn: async (): Promise<Record<string, number>> => {
        const { data } = await api.get<HybridSearchResponse>(API.search.hybrid, {
          // tool_filters 미전달 → 전체 풀 기준 분포. limit=1로 payload 최소화.
          params: { keyword, limit: 1, offset: 0 },
          paramsSerializer: serializeListParams,
        });
        return data.source_distribution;
      },
      enabled: keyword.trim().length > 0,
      staleTime: 60_000,
    }),
};
