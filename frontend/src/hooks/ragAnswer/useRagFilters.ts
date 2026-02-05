/**
 * useRagFilters
 * GitHub, Jira 탐색기 및 필터 선택 상태 관리
 */

'use client';

import { useState, useCallback } from 'react';
import type { GithubNode } from '@/constants/githubRepoData';
import type { JiraNode } from '@/constants/jiraData';
import { getAllChildIds } from '@/util/tree';

export type ExplorerType = 'github' | 'jira' | null;

interface UseRagFiltersReturn {
  // Filter Bar State
  isFilterOpen: boolean;
  toggleFilter: () => void;

  // Explorer State
  activeExplorer: ExplorerType;
  setActiveExplorer: React.Dispatch<React.SetStateAction<ExplorerType>>;
  handleGithubClick: () => void;
  handleJiraClick: () => void;

  // People Filter
  selectedPeople: string[];
  togglePerson: (val: string) => void;

  // GitHub Filter
  selectedGithubItems: GithubNode[];
  toggleGithubItem: (item: GithubNode) => void;
  currentRepo: GithubNode | null;
  setCurrentRepo: React.Dispatch<React.SetStateAction<GithubNode | null>>;

  // Jira Filter
  selectedJiraItems: JiraNode[];
  toggleJiraItem: (item: JiraNode) => void;
  currentJiraProject: JiraNode | null;
  setCurrentJiraProject: React.Dispatch<React.SetStateAction<JiraNode | null>>;

  // Popover State
  openPopover: 'person' | 'department' | 'project' | null;
  setOpenPopover: React.Dispatch<React.SetStateAction<'person' | 'department' | 'project' | null>>;

  // Computed Labels
  personLabel: string;
  gitLabel: string;
  jiraLabel: string;

  // Actions
  handleResetAll: () => void;
}

export const useRagFilters = (): UseRagFiltersReturn => {
  // Filter Bar
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [activeExplorer, setActiveExplorer] = useState<ExplorerType>(null);

  // Popover
  const [openPopover, setOpenPopover] = useState<'person' | 'department' | 'project' | null>(null);

  // People
  const [selectedPeople, setSelectedPeople] = useState<string[]>([]);

  // GitHub
  const [selectedGithubItems, setSelectedGithubItems] = useState<GithubNode[]>([]);
  const [currentRepo, setCurrentRepo] = useState<GithubNode | null>(null);

  // Jira
  const [selectedJiraItems, setSelectedJiraItems] = useState<JiraNode[]>([]);
  const [currentJiraProject, setCurrentJiraProject] = useState<JiraNode | null>(null);

  /** 필터 바 토글 */
  const toggleFilter = useCallback(() => {
    setIsFilterOpen((prev) => {
      const nextState = !prev;
      if (!nextState) {
        setActiveExplorer(null);
      }
      return nextState;
    });
  }, []);

  /** GitHub 탐색기 토글 */
  const handleGithubClick = useCallback(() => {
    setActiveExplorer((prev) => (prev === 'github' ? null : 'github'));
  }, []);

  /** Jira 탐색기 토글 */
  const handleJiraClick = useCallback(() => {
    setActiveExplorer((prev) => (prev === 'jira' ? null : 'jira'));
  }, []);

  /** 담당자 선택 토글 */
  const togglePerson = useCallback((val: string) => {
    setSelectedPeople((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  }, []);

  /** GitHub 항목 선택 토글 */
  const toggleGithubItem = useCallback((item: GithubNode) => {
    setSelectedGithubItems((prev) => {
      const exists = prev.find((i) => i.id === item.id);

      if (exists) {
        const idsToRemove = getAllChildIds(item);
        return prev.filter((i) => !idsToRemove.includes(i.id));
      } else {
        return [...prev, item];
      }
    });
  }, []);

  /** Jira 항목 선택 토글 */
  const toggleJiraItem = useCallback((item: JiraNode) => {
    setSelectedJiraItems((prev) => {
      const exists = prev.find((i) => i.id === item.id);

      if (exists) {
        const idsToRemove = getAllChildIds(item);
        return prev.filter((i) => !idsToRemove.includes(i.id));
      } else {
        return [...prev, item];
      }
    });
  }, []);

  /** 전체 필터 초기화 */
  const handleResetAll = useCallback(() => {
    setSelectedPeople([]);
    setSelectedGithubItems([]);
    setSelectedJiraItems([]);
  }, []);

  // Labels
  const personLabel = selectedPeople.length > 0 ? `담당자: ${selectedPeople[0]} 외` : '담당자';
  const gitLabel = selectedGithubItems.length > 0 ? `Github: ${selectedGithubItems[0].name} 외` : 'Github';
  const jiraLabel = selectedJiraItems.length > 0 ? `Jira: ${selectedJiraItems[0].name} 외` : 'Jira';

  return {
    // Filter Bar
    isFilterOpen,
    toggleFilter,

    // Explorer
    activeExplorer,
    setActiveExplorer,
    handleGithubClick,
    handleJiraClick,

    // People
    selectedPeople,
    togglePerson,

    // GitHub
    selectedGithubItems,
    toggleGithubItem,
    currentRepo,
    setCurrentRepo,

    // Jira
    selectedJiraItems,
    toggleJiraItem,
    currentJiraProject,
    setCurrentJiraProject,

    // Popover
    openPopover,
    setOpenPopover,

    // Computed
    personLabel,
    gitLabel,
    jiraLabel,

    // Actions
    handleResetAll,
  };
};

export default useRagFilters;
