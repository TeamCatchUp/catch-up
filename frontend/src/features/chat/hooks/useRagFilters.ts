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

  // People Filter
  selectedPeople: string[];
  togglePerson: (val: string) => void;

  // Popover State
  openPopover: 'person' | 'department' | 'project' | null;
  setOpenPopover: React.Dispatch<React.SetStateAction<'person' | 'department' | 'project' | null>>;

  // Computed Labels
  personLabel: string;

  // Actions
  handleResetAll: () => void;
}

export const useRagFilters = (): UseRagFiltersReturn => {
  // Filter Bar
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  // 소스 토글
  const [selectedSources, setSelectedSources] = useState<SourceType[]>([]);

  const toggleSource = useCallback((source: SourceType) => {
    setSelectedSources((prev) => (prev.includes(source) ? prev.filter((s) => s !== source) : [...prev, source]));
  }, []);

  // Popover
  const [openPopover, setOpenPopover] = useState<'person' | 'department' | 'project' | null>(null);

  // People
  const [selectedPeople, setSelectedPeople] = useState<string[]>([]);

  /** 필터 바 토글 */
  const toggleFilter = useCallback(() => {
    setIsFilterOpen((prev) => !prev);
  }, []);

  /** 담당자 선택 토글 */
  const togglePerson = useCallback((val: string) => {
    setSelectedPeople((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  }, []);

  /** 전체 필터 초기화 */
  const handleResetAll = useCallback(() => {
    setSelectedPeople([]);
  }, []);

  // Labels
  const personLabel = selectedPeople.length > 0 ? `담당자: ${selectedPeople[0]} 외` : '담당자';

  return {
    isFilterOpen,
    toggleFilter,
    selectedSources,
    toggleSource,
    selectedPeople,
    togglePerson,
    openPopover,
    setOpenPopover,
    personLabel,
    handleResetAll,
  };
};

export default useRagFilters;
