'use client';

// Figma 13426:54282 — ResultSearchBar(collapsed) + AccentTabs.
// 외부: border-b flex flex-col items-center pt-5 px-16
// 내부: max-w-[1420px] w-full flex flex-col gap-5

import { useQuery } from '@tanstack/react-query';

import AccentTabs, { type AccentTabItem } from '@/shared/components/ui/accent-tabs';

import { hybridSearchQueries } from '../queries/hybridSearch.queries';
import type { ToolFilter } from '../types/hybridSearchApi';
import ResultSearchBar from './ResultSearchBar';

type ActiveTab = 'all' | ToolFilter;

interface ResultPageHeaderProps {
  // 확정된 검색어 — distribution 호출용
  keyword: string;
  // 입력 중 임시값
  draftKeyword: string;
  onDraftKeywordChange: (v: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  activeTab: ActiveTab;
  onTabChange: (next: ActiveTab) => void;
}

function buildTabItems(dist: Record<string, number> | undefined): AccentTabItem<ActiveTab>[] {
  return [
    { value: 'all', label: '전체' },
    { value: 'confluence', label: 'Confluence', count: dist?.confluence ?? 0 },
    { value: 'jira', label: 'Jira', count: dist?.jira ?? 0 },
    { value: 'slack', label: 'Slack', count: dist?.slack ?? 0 },
    { value: 'github', label: 'Github', count: dist?.github ?? 0 },
    { value: 'channel_talk', label: '채널톡', count: dist?.channel_talk ?? 0 },
  ];
}

export default function ResultPageHeader({
  keyword,
  draftKeyword,
  onDraftKeywordChange,
  onSubmit,
  onClear,
  activeTab,
  onTabChange,
}: ResultPageHeaderProps) {
  const { data: distribution } = useQuery(hybridSearchQueries.distribution(keyword));
  const tabItems = buildTabItems(distribution);

  return (
    <header className="border-edge-normal flex w-full flex-col items-center border-b px-16 pt-5">
      <div className="flex w-full max-w-[1420px] flex-col items-start gap-5">
        <ResultSearchBar
          value={draftKeyword}
          onValueChange={onDraftKeywordChange}
          onSubmit={onSubmit}
          onClear={onClear}
        />
        <AccentTabs
          items={tabItems}
          value={activeTab}
          onValueChange={onTabChange}
          ariaLabel="결과 필터 탭"
        />
      </div>
    </header>
  );
}
