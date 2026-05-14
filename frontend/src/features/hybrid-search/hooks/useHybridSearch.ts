'use client';

// hybridSearch list query + 응답 도착 시 검색 기록 cache 무효화.
// active가 scope 밖이면 fetch skip (isOutOfScope 반환 → 호출자가 EmptyState 분기).

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { searchHistoryQueries } from '@/shared/queries/searchHistory.queries';

import { hybridSearchQueries } from '../queries/hybridSearch.queries';
import type { ToolFilter } from '../types/hybridSearchApi';
import type { ActiveTab } from './useHybridSearchUrlState';

interface UseHybridSearchParams {
  keyword: string;
  scope: ToolFilter[];
  active: ActiveTab;
  page: number;
}

function computeIsActiveInScope(scope: ToolFilter[], active: ActiveTab): boolean {
  if (active === 'all') return true;
  if (scope.length === 0) return true;
  return scope.includes(active);
}

export function useHybridSearch(params: UseHybridSearchParams) {
  const queryClient = useQueryClient();

  const isActiveInScope = computeIsActiveInScope(params.scope, params.active);

  const query = useQuery({
    ...hybridSearchQueries.list(params),
    // scope 밖 active면 list 호출 skip — UI는 EmptyState 보여줌.
    enabled: params.keyword.trim().length > 0 && isActiveInScope,
  });

  // dataUpdatedAt 갱신 시(매 새 응답마다) 검색 기록 cache 무효화.
  useEffect(() => {
    if (query.isSuccess) {
      queryClient.invalidateQueries({ queryKey: searchHistoryQueries.all() });
    }
  }, [query.dataUpdatedAt, query.isSuccess, queryClient]);

  return Object.assign(query, { isOutOfScope: !isActiveInScope });
}
