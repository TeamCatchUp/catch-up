'use client';

import type { UseSearchFiltersReturn } from '@/features/search/hooks/useSearchFilters';

import { GithubExplorer } from '@/shared/components/query/explorer/GithubExplorer';
import { JiraExplorer } from '@/shared/components/query/explorer/JiraExplorer';
import { RecentActivityExplorer } from '@/shared/components/query/recent/RecentActivityExplorer';

interface ExplorerPanelProps {
  filters: UseSearchFiltersReturn;
}

export default function ExplorerPanel({ filters }: ExplorerPanelProps) {
  return (
    <div className="no-scrollbar flex min-h-0 flex-1 flex-col items-start gap-2 self-stretch overflow-y-auto pt-2">
      {filters.explorerMode === 'github' ? (
        <GithubExplorer
          selectedItems={filters.selectedGithubItems.map((i) => i.id)}
          onToggleItem={filters.toggleGithubItem}
          currentRepo={filters.currentRepo}
          onNavigate={filters.setCurrentRepo}
          onClickBack={filters.handleGithubClick}
        />
      ) : filters.explorerMode === 'jira' ? (
        <JiraExplorer
          selectedItems={filters.selectedJiraItems.map((i) => i.id)}
          onToggleItem={filters.toggleJiraItem}
          currentProject={filters.currentJiraProject}
          onNavigate={filters.setCurrentJiraProject}
          onClickBack={filters.handleJiraClick}
        />
      ) : (
        <RecentActivityExplorer />
      )}
    </div>
  );
}
