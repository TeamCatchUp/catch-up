// 검색 기록 조회 hook. useQuery + API → UI 모델 매핑만.
// 그룹화/슬라이스는 SearchHistoryList 컴포넌트가 담당.
// backend 응답이 array로 바뀜 (PR #689) — 직접 .map.

import { useQuery } from '@tanstack/react-query';

import { searchHistoryQueries } from '@/shared/queries/searchHistory.queries';
import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import { mapSearchHistory } from '@/shared/utils/mapSearchHistory';

export interface UseSearchHistoryEntriesResult {
  entries: SearchHistoryEntry[];
  isLoading: boolean;
}

export function useSearchHistoryEntries(): UseSearchHistoryEntriesResult {
  const { data, isLoading } = useQuery(searchHistoryQueries.list());

  return {
    entries: (data ?? []).map(mapSearchHistory),
    isLoading,
  };
}
