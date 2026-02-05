import type { GithubNode } from '@/constants/shared/githubRepoData';
import type { JiraNode } from '@/constants/shared/jiraData';

/** Popover 타입 */
export type PopoverType = 'person' | 'department' | 'project' | null;

/** Explorer 모드 타입 */
export type ExplorerMode = 'github' | 'jira' | null;

/** 필터 칩 데이터 */
export interface ChipData {
  id: string;
  name: string;
  Icon: React.ComponentType<{ className?: string }>;
  onRemove: () => void;
}

/** 필터 레이블 */
export interface FilterLabels {
  person: string;
  dept: string;
  project: string;
  git: string;
  jira: string;
}
