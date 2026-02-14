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

  // 필터 선택
  selectedPeople: string[];
  togglePerson: (val: string) => void;
  selectedDepts: string[];
  toggleDept: (val: string) => void;
  selectedProjects: string[];
  toggleProject: (val: string) => void;

  // Popover State
  openPopover: 'person' | 'department' | 'project' | null;
  setOpenPopover: React.Dispatch<React.SetStateAction<'person' | 'department' | 'project' | null>>;

  // Computed Labels
  personLabel: string;
  deptLabel: string;
  projectLabel: string;

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

  // 필터 상태
  const [selectedPeople, setSelectedPeople] = useState<string[]>([]);
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);

  /** 필터 바 토글 */
  const toggleFilter = useCallback(() => {
    setIsFilterOpen((prev) => !prev);
  }, []);

  /** 토글 핸들러 */
  const togglePerson = useCallback((val: string) => {
    setSelectedPeople((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  }, []);

  const toggleDept = useCallback((val: string) => {
    setSelectedDepts((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  }, []);

  const toggleProject = useCallback((val: string) => {
    setSelectedProjects((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  }, []);

  // Labels
  const personLabel = selectedPeople.length > 0 ? `담당자: ${selectedPeople[0]} 외` : '담당자';
  const deptLabel = selectedDepts.length > 0 ? `부서: ${selectedDepts[0]} 외` : '부서';
  const projectLabel = selectedProjects.length > 0 ? `프로젝트: ${selectedProjects[0]} 외` : '프로젝트';

  return {
    isFilterOpen,
    toggleFilter,
    selectedSources,
    toggleSource,
    selectedPeople,
    togglePerson,
    selectedDepts,
    toggleDept,
    selectedProjects,
    toggleProject,
    openPopover,
    setOpenPopover,
    personLabel,
    deptLabel,
    projectLabel,
  };
};

export default useRagFilters;
