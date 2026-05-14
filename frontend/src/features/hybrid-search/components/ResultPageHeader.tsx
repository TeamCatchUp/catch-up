'use client';

// Figma 13426:54282 — ResultSearchBar(collapsed) + AccentTabs.
// distribution은 list 응답의 results에서 client-side 계산 (별도 fetch 없음).
// ResultListSection과 같은 list queryKey 사용 → cache 공유로 fetch 1회.

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import AccentTabs, { type AccentTabItem } from '@/shared/components/ui/accent-tabs';

import { hybridSearchQueries } from '../queries/hybridSearch.queries';
import type { ActiveTab, ToolFilter } from '../types/hybridSearchApi';
import ResultSearchBar from './ResultSearchBar';

interface ResultPageHeaderProps {
  // 확정된 검색어 — list query 호출에 사용
  keyword: string;
  // scope: list query 호출에 사용
  scope: ToolFilter[];
  // 입력 중 임시값
  draftKeyword: string;
  onDraftKeywordChange: (v: string) => void;
  // expanded 검색바 안 chips의 draft 상태 (submit 시 적용)
  draftChips: ToolFilter[];
  onDraftChipsChange: (next: ToolFilter[]) => void;
  onSubmit: () => void;
  onClear: () => void;
  activeTab: ActiveTab;
  onTabChange: (next: ActiveTab) => void;
}

function buildTabItems(dist: Record<string, number>): AccentTabItem<ActiveTab>[] {
  return [
    { value: 'all', label: '전체' },
    { value: 'confluence', label: 'Confluence', count: dist.confluence ?? 0 },
    { value: 'jira', label: 'Jira', count: dist.jira ?? 0 },
    { value: 'slack', label: 'Slack', count: dist.slack ?? 0 },
    { value: 'github', label: 'Github', count: dist.github ?? 0 },
    { value: 'channel_talk', label: '채널톡', count: dist.channel_talk ?? 0 },
  ];
}

export default function ResultPageHeader({
  keyword,
  scope,
  draftKeyword,
  onDraftKeywordChange,
  draftChips,
  onDraftChipsChange,
  onSubmit,
  onClear,
  activeTab,
  onTabChange,
}: ResultPageHeaderProps) {
  // ResultListSection과 같은 queryKey → cache 자동 공유, fetch 1회만.
  const query = useQuery(hybridSearchQueries.list({ keyword, scope }));

  // results에서 source별 count 직접 계산 — backend의 source_distribution 의존 X.
  const distribution = useMemo(() => {
    const counts: Record<string, number> = {};
    if (query.data) {
      for (const r of query.data.results) {
        counts[r.source] = (counts[r.source] ?? 0) + 1;
      }
    }
    return counts;
  }, [query.data]);

  const tabItems = buildTabItems(distribution);

  return (
    <header className="border-edge-normal flex w-full flex-col items-center border-b px-16 pt-5">
      <div className="flex w-full max-w-[1260px] flex-col items-start gap-5">
        <ResultSearchBar
          value={draftKeyword}
          onValueChange={onDraftKeywordChange}
          chips={draftChips}
          onChipsChange={onDraftChipsChange}
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
