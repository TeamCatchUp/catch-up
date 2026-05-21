/**
 * useRagFilters
 * 채팅 필터 선택 상태 관리
 */

'use client';

import { useCallback, useState } from 'react';

import type { DocsSource } from '@/shared/types/source';

export interface UseRagFiltersReturn {
  // Filter Bar State
  isFilterOpen: boolean;
  toggleFilter: () => void;

  // 소스 선택
  selectedSources: DocsSource[];
  setSelectedSources: (next: DocsSource[]) => void;
}

interface UseRagFiltersOptions {
  initialSources?: DocsSource[];
}

export default function useRagFilters(options?: UseRagFiltersOptions): UseRagFiltersReturn {
  // Filter Bar — initialSources가 있으면 자동으로 열기
  const [isFilterOpen, setIsFilterOpen] = useState(Boolean(options?.initialSources?.length));

  // 소스 선택
  const [selectedSources, setSelectedSources] = useState<DocsSource[]>(options?.initialSources ?? []);

  /** 필터 바 토글 */
  const toggleFilter = useCallback(() => {
    setIsFilterOpen((prev) => !prev);
  }, []);

  return {
    isFilterOpen,
    toggleFilter,
    selectedSources,
    setSelectedSources,
  };
}
