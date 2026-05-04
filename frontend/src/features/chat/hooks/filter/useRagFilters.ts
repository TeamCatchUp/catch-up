/**
 * useRagFilters
 * 채팅 필터 선택 상태 관리
 */

'use client';

import { useCallback, useState } from 'react';

import type { SourceType } from '@/shared/hooks/query/useSearchFilters';

export interface UseRagFiltersReturn {
  // Filter Bar State
  isFilterOpen: boolean;
  toggleFilter: () => void;

  // 소스 토글
  selectedSources: SourceType[];
  toggleSource: (source: SourceType) => void;
}

interface UseRagFiltersOptions {
  initialSources?: SourceType[];
}

export default function useRagFilters(options?: UseRagFiltersOptions): UseRagFiltersReturn {
  // Filter Bar — initialSources가 있으면 자동으로 열기
  const [isFilterOpen, setIsFilterOpen] = useState(Boolean(options?.initialSources?.length));

  // 소스 토글
  const [selectedSources, setSelectedSources] = useState<SourceType[]>(options?.initialSources ?? []);

  const toggleSource = useCallback((source: SourceType) => {
    setSelectedSources((prev) => (prev.includes(source) ? prev.filter((s) => s !== source) : [...prev, source]));
  }, []);

  /** 필터 바 토글 */
  const toggleFilter = useCallback(() => {
    setIsFilterOpen((prev) => !prev);
  }, []);

  return {
    isFilterOpen,
    toggleFilter,
    selectedSources,
    toggleSource,
  };
}
