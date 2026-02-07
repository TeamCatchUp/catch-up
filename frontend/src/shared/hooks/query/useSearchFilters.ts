/**
 * useSearchFilters
 * 검색 페이지의 필터 상태 관리 훅
 */

'use client';

import { useState, useCallback, useMemo } from 'react';
import type { GithubNode } from '@/shared/types/query/github';
import type { JiraNode } from '@/shared/types/query/jira';
import { getAllChildIds } from '@/shared/utils/tree';
import type { PopoverType, ExplorerMode, ChipData, FilterLabels } from '@/shared/types/query/search';

// Icons
import IconPerson from '@/public/icons/icon/person.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconFolder from '@/public/icons/icon/folder_blue.svg';
import IconFile from '@/public/icons/icon/file_filled.svg';
import IconJiraTicket from '@/public/icons/jira/Task.svg';
import IconJiraSprint from '@/public/icons/jira/Epic.svg';

export interface UseSearchFiltersReturn {
  // Explorer 모드
  explorerMode: ExplorerMode;
  handleGithubClick: () => void;
  handleJiraClick: () => void;

  // Popover
  openPopover: PopoverType;
  setOpenPopover: React.Dispatch<React.SetStateAction<PopoverType>>;

  // 필터 선택
  selectedPeople: string[];
  togglePerson: (val: string) => void;
  selectedDepts: string[];
  toggleDept: (val: string) => void;
  selectedProjects: string[];
  toggleProject: (val: string) => void;

  // GitHub
  selectedGithubItems: GithubNode[];
  toggleGithubItem: (item: GithubNode) => void;
  currentRepo: GithubNode | null;
  setCurrentRepo: React.Dispatch<React.SetStateAction<GithubNode | null>>;

  // Jira
  selectedJiraItems: JiraNode[];
  toggleJiraItem: (item: JiraNode) => void;
  currentJiraProject: JiraNode | null;
  setCurrentJiraProject: React.Dispatch<React.SetStateAction<JiraNode | null>>;

  // Computed
  labels: FilterLabels;
  allSelectedChips: ChipData[];

  // Actions
  handleResetAll: () => void;
}

export const useSearchFilters = (): UseSearchFiltersReturn => {
  // Explorer 모드 (기존 selectedOptions 대체)
  const [explorerMode, setExplorerMode] = useState<ExplorerMode>(null);

  // Popover
  const [openPopover, setOpenPopover] = useState<PopoverType>(null);

  // 필터 상태
  const [selectedPeople, setSelectedPeople] = useState<string[]>([]);
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);

  // GitHub
  const [selectedGithubItems, setSelectedGithubItems] = useState<GithubNode[]>([]);
  const [currentRepo, setCurrentRepo] = useState<GithubNode | null>(null);

  // Jira
  const [selectedJiraItems, setSelectedJiraItems] = useState<JiraNode[]>([]);
  const [currentJiraProject, setCurrentJiraProject] = useState<JiraNode | null>(null);

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

  const toggleGithubItem = useCallback((item: GithubNode) => {
    setSelectedGithubItems((prev) => {
      const exists = prev.find((i) => i.id === item.id);
      if (exists) {
        const idsToRemove = getAllChildIds(item);
        return prev.filter((i) => !idsToRemove.includes(i.id));
      }
      return [...prev, item];
    });
  }, []);

  const toggleJiraItem = useCallback((item: JiraNode) => {
    setSelectedJiraItems((prev) => {
      const exists = prev.find((i) => i.id === item.id);
      if (exists) {
        const idsToRemove = getAllChildIds(item);
        return prev.filter((i) => !idsToRemove.includes(i.id));
      }
      return [...prev, item];
    });
  }, []);

  // Explorer mode handlers
  const handleGithubClick = useCallback(() => {
    setExplorerMode((prev) => {
      if (prev === 'github') {
        setCurrentRepo(null);
        return null;
      }
      return 'github';
    });
  }, []);

  const handleJiraClick = useCallback(() => {
    setExplorerMode((prev) => {
      if (prev === 'jira') {
        setCurrentJiraProject(null);
        return null;
      }
      return 'jira';
    });
  }, []);

  // Reset all
  const handleResetAll = useCallback(() => {
    setSelectedPeople([]);
    setSelectedDepts([]);
    setSelectedProjects([]);
    setSelectedGithubItems([]);
    setSelectedJiraItems([]);
  }, []);

  // Computed: Labels
  const labels = useMemo<FilterLabels>(
    () => ({
      person: selectedPeople.length > 0 ? `담당자: ${selectedPeople[0]} 외` : '담당자',
      dept: selectedDepts.length > 0 ? `부서: ${selectedDepts[0]} 외` : '부서명',
      project: selectedProjects.length > 0 ? `프로젝트: ${selectedProjects[0]} 외` : '프로젝트',
      git: selectedGithubItems.length > 0 ? `Github: ${selectedGithubItems[0].name} 외` : 'Github',
      jira: selectedJiraItems.length > 0 ? `Jira: ${selectedJiraItems[0].name} 외` : 'Jira',
    }),
    [selectedPeople, selectedDepts, selectedProjects, selectedGithubItems, selectedJiraItems],
  );

  // Computed: All selected chips (부모-자식 중복 필터링 포함)
  const allSelectedChips = useMemo<ChipData[]>(() => {
    const filterParentSelected = <T extends { id: string; children?: T[] }>(items: T[], allItems: T[]) =>
      items.filter((item) => {
        return !allItems.some((parent) => {
          if (parent.id === item.id) return false;
          return parent.children?.some((child) => child.id === item.id);
        });
      });

    return [
      ...selectedPeople.map((name) => ({
        id: `person-${name}`,
        name,
        Icon: IconPerson,
        onRemove: () => togglePerson(name),
      })),
      ...selectedDepts.map((name) => ({
        id: `dept-${name}`,
        name,
        Icon: IconTag,
        onRemove: () => toggleDept(name),
      })),
      ...selectedProjects.map((name) => ({
        id: `project-${name}`,
        name,
        Icon: IconSpace,
        onRemove: () => toggleProject(name),
      })),
      ...filterParentSelected(selectedGithubItems, selectedGithubItems).map((item) => ({
        id: item.id,
        name: item.name,
        Icon: item.type === 'repo' ? IconGithub : item.type === 'tree' ? IconFolder : IconFile,
        onRemove: () => toggleGithubItem(item),
      })),
      ...filterParentSelected(selectedJiraItems, selectedJiraItems).map((item) => ({
        id: item.id,
        name: item.name,
        Icon: item.type === 'project' ? IconJira : item.type === 'board' ? IconJiraSprint : IconJiraTicket,
        onRemove: () => toggleJiraItem(item),
      })),
    ];
  }, [
    selectedPeople,
    selectedDepts,
    selectedProjects,
    selectedGithubItems,
    selectedJiraItems,
    togglePerson,
    toggleDept,
    toggleProject,
    toggleGithubItem,
    toggleJiraItem,
  ]);

  return {
    explorerMode,
    handleGithubClick,
    handleJiraClick,
    openPopover,
    setOpenPopover,
    selectedPeople,
    togglePerson,
    selectedDepts,
    toggleDept,
    selectedProjects,
    toggleProject,
    selectedGithubItems,
    toggleGithubItem,
    currentRepo,
    setCurrentRepo,
    selectedJiraItems,
    toggleJiraItem,
    currentJiraProject,
    setCurrentJiraProject,
    labels,
    allSelectedChips,
    handleResetAll,
  };
};
