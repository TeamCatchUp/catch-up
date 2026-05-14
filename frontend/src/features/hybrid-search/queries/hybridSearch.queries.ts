import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { ActiveTab } from '../hooks/useHybridSearchUrlState';
import type { HybridSearchResponse, ToolFilter } from '../types/hybridSearchApi';

export const HYBRID_SEARCH_PAGE_SIZE = 7;

interface ListParams {
  keyword: string;
  scope: ToolFilter[];
  active: ActiveTab;
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

  // 결과 리스트 — scope + active 변경에 반응.
  // active='all' → scope 전체로 호출, active=source → 그 source만.
  list: (params: ListParams) =>
    queryOptions({
      queryKey: [...hybridSearchQueries.all(), 'list', params] as const,
      queryFn: async (): Promise<HybridSearchResponse> => {
        const effectiveFilters = params.active === 'all' ? params.scope : [params.active];
        const { data } = await api.get<HybridSearchResponse>(API.search.hybrid, {
          params: {
            keyword: params.keyword,
            limit: HYBRID_SEARCH_PAGE_SIZE,
            offset: (params.page - 1) * HYBRID_SEARCH_PAGE_SIZE,
            tool_filters: effectiveFilters.length > 0 ? effectiveFilters : undefined,
          },
          paramsSerializer: serializeListParams,
        });
        return data;
      },
      enabled: params.keyword.trim().length > 0,
      staleTime: 30_000,
    }),

  // AccentTabs용 source_distribution — keyword + scope에 의존(active 무관).
  // scope=tools (chips 선택)일 땐 그 풀 기준 분포, scope=[] (5종 fallback)일 땐 전체 풀.
  // → AccentTabs count가 stable, active 클릭 시 cache hit.
  distribution: (keyword: string, scope: ToolFilter[]) =>
    queryOptions({
      queryKey: [...hybridSearchQueries.all(), 'distribution', keyword, scope] as const,
      queryFn: async (): Promise<Record<string, number>> => {
        const { data } = await api.get<HybridSearchResponse>(API.search.hybrid, {
          params: {
            keyword,
            limit: 1,
            offset: 0,
            tool_filters: scope.length > 0 ? scope : undefined,
          },
          paramsSerializer: serializeListParams,
        });
        return data.source_distribution;
      },
      enabled: keyword.trim().length > 0,
      staleTime: 60_000,
    }),
};
