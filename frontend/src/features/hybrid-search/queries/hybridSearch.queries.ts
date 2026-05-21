import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import { toApiTemporalParams } from '@/shared/utils/temporalRange';

import type { HybridSearchResponse, ToolFilter } from '../types/hybridSearchApi';

// client-side pagination 단위. backend는 최대 50개 dedup 결과 한 번에 반환.
export const HYBRID_SEARCH_PAGE_SIZE = 10;

interface ListParams {
  keyword: string;
  scope: ToolFilter[];
  /** yyyy-MM-dd KST 일자. 미지정 시 기간 필터 없음. */
  start?: string;
  end?: string;
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

  // 결과 리스트 — keyword + scope에만 의존. active/page는 client-side에서 처리.
  // backend는 dedup 후 최대 50개 전체를 반환 (limit/offset 무시).
  list: (params: ListParams) =>
    queryOptions({
      queryKey: [...hybridSearchQueries.all(), 'list', params] as const,
      queryFn: async (): Promise<HybridSearchResponse> => {
        const { data } = await api.get<HybridSearchResponse>(API.search.hybrid, {
          params: {
            keyword: params.keyword,
            tool_filters: params.scope.length > 0 ? params.scope : undefined,
            ...toApiTemporalParams(params.start, params.end),
          },
          paramsSerializer: serializeListParams,
        });
        return data;
      },
      enabled: params.keyword.trim().length > 0,
      staleTime: 30_000,
    }),
};
