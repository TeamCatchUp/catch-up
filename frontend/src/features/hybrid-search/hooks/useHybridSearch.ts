'use client';

// hybridSearch list query + 응답 도착 시 검색 기록 cache 무효화.
// active/page는 client-side state라 본 hook은 keyword + scope만 받음.

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { searchHistoryQueries } from '@/shared/queries/searchHistory.queries';

import { hybridSearchQueries } from '../queries/hybridSearch.queries';
import type { ToolFilter } from '../types/hybridSearchApi';

interface UseHybridSearchParams {
  keyword: string;
  scope: ToolFilter[];
  start?: string;
  end?: string;
}

export function useHybridSearch(params: UseHybridSearchParams) {
  const queryClient = useQueryClient();
  const query = useQuery({
    ...hybridSearchQueries.list(params),
    enabled: params.keyword.trim().length > 0,
  });

  // dataUpdatedAt 갱신 시(매 새 응답마다) 검색 기록 cache 무효화.
  useEffect(() => {
    if (query.isSuccess) {
      queryClient.invalidateQueries({ queryKey: searchHistoryQueries.all() });
    }
  }, [query.dataUpdatedAt, query.isSuccess, queryClient]);

  return query;
}
