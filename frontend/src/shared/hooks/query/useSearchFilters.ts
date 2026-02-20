/**
 * useSearchFilters
 * 검색 페이지의 필터 상태 관리 훅
 */

'use client';

import { useCallback, useMemo, useState } from 'react';

import type { FilterLabels, PopoverType } from '@/shared/types/query/search';

export type SourceType = 'jira' | 'github' | 'slack' | 'confluence';

export interface UseSearchFiltersReturn {
  // Popover
  openPopover: PopoverType;
  setOpenPopover: React.Dispatch<React.SetStateAction<PopoverType>>;

  // 소스 토글
  selectedSources: SourceType[];
  toggleSource: (source: SourceType) => void;

  // 필터 선택
  selectedPeople: string[];
  togglePerson: (val: string) => void;
  selectedDepts: string[];
  toggleDept: (val: string) => void;
  selectedProjects: string[];
  toggleProject: (val: string) => void;

  // Computed
  labels: FilterLabels;
}

export const useSearchFilters = (): UseSearchFiltersReturn => {
  // Popover
  const [openPopover, setOpenPopover] = useState<PopoverType>(null);

  // 소스 토글
  const [selectedSources, setSelectedSources] = useState<SourceType[]>([]);

  const toggleSource = useCallback((source: SourceType) => {
    setSelectedSources((prev) => (prev.includes(source) ? prev.filter((s) => s !== source) : [...prev, source]));
  }, []);

  // 필터 상태
  const [selectedPeople, setSelectedPeople] = useState<string[]>([]);
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);

  // Toggle handlers
  const togglePerson = useCallback((val: string) => {
    setSelectedPeople((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  }, []);

  const toggleDept = useCallback((val: string) => {
    setSelectedDepts((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  }, []);

  const toggleProject = useCallback((val: string) => {
    setSelectedProjects((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  }, []);

  // Computed: Labels
  const labels = useMemo<FilterLabels>(
    () => ({
      person: selectedPeople.length > 0 ? `담당자: ${selectedPeople[0]} 외` : '담당자',
      dept: selectedDepts.length > 0 ? `부서: ${selectedDepts[0]} 외` : '부서명',
      project: selectedProjects.length > 0 ? `프로젝트: ${selectedProjects[0]} 외` : '프로젝트',
    }),
    [selectedPeople, selectedDepts, selectedProjects],
  );

  return {
    openPopover,
    setOpenPopover,
    selectedPeople,
    togglePerson,
    selectedDepts,
    toggleDept,
    selectedProjects,
    toggleProject,
    labels,
    selectedSources,
    toggleSource,
  };
};
