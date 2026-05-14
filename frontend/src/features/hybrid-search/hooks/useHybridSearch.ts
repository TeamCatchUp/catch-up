'use client';

// hybridSearch list query + 응답 도착 시 검색 기록 cache 무효화.
// backend가 /hybrid 호출 시 자동으로 manual_search_history에 기록하므로
// 응답 후 docs 모드의 검색 기록 영역이 즉시 갱신되도록 invalidate.

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { searchHistoryQueries } from '@/shared/queries/searchHistory.queries';

import { hybridSearchQueries } from '../queries/hybridSearch.queries';
import type { ToolFilter } from '../types/hybridSearchApi';

interface UseHybridSearchParams {
  keyword: string;
  tools: ToolFilter[];
  page: number;
}

export function useHybridSearch(params: UseHybridSearchParams) {
  const queryClient = useQueryClient();
  const query = useQuery(hybridSearchQueries.list(params));

  // dataUpdatedAt이 갱신될 때마다(매 새 응답마다) invalidate.
  useEffect(() => {
    if (query.isSuccess) {
      queryClient.invalidateQueries({ queryKey: searchHistoryQueries.all() });
    }
  }, [query.dataUpdatedAt, query.isSuccess, queryClient]);

  return query;
}
