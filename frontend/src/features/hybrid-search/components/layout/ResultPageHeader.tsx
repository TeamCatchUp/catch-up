'use client';

// ResultSearchBar(collapsed) + AccentTabs.
// distribution은 list 응답의 results에서 client-side 계산 (별도 fetch 없음).
// ResultListSection과 같은 list queryKey 사용 → cache 공유로 fetch 1회.

import { useMemo } from 'react';
import type { DateRange } from 'react-day-picker';
import { useQuery } from '@tanstack/react-query';

import AccentTabs, { type AccentTabItem } from '@/shared/components/ui/accent-tabs';
import { dateRangeToUrlParams, type SortOrder } from '@/shared/utils/temporalRange';

import { hybridSearchQueries } from '../../queries/hybridSearch.queries';
import type { ActiveTab, ToolFilter } from '../../types/hybridSearchApi';
import SortDropdown from '../result-list/SortDropdown';
import ResultSearchBar from '../search-bar/ResultSearchBar';

interface ResultPageHeaderProps {
  // 확정된 검색어 — list query 호출에 사용
  keyword: string;
  // API 전송용 수동 tool filters. 비어 있으면 Smart Filter의 tool 추론을 허용한다.
  toolFilters: ToolFilter[];
  // 입력 중 임시값
  draftKeyword: string;
  onDraftKeywordChange: (v: string) => void;
  // expanded 검색바 안 chips의 draft 상태 (submit 시 적용)
  draftChips: ToolFilter[];
  onDraftChipsChange: (next: ToolFilter[]) => void;
  // 확정 기간 — list query에 사용
  dateRange: DateRange | undefined;
  // 입력 중 임시 기간 — 검색바 필터에 사용, submit 시 적용
  draftDateRange: DateRange | undefined;
  onDraftDateRangeChange: (next: DateRange | undefined) => void;
  // URL/API에 적용된 현재 결과 기준 상태
  smartFilter: boolean;
  // expanded 검색바 안 smart filter draft 상태 (submit 시 적용)
  draftSmartFilter: boolean;
  onDraftSmartFilterChange: (next: boolean) => void;
  onSubmit: () => void;
  onHistorySubmit: (query: string) => void;
  onClear: () => void;
  onAiModeClick: () => void;
  activeTab: ActiveTab;
  onTabChange: (next: ActiveTab) => void;
  // 결과 정렬 — 클라이언트 사이드
  sortOrder: SortOrder;
  onSortChange: (next: SortOrder) => void;
}

// 데이터 도착 후엔 count=0인 source 탭은 숨김. 로딩 중엔 모든 탭을 count badge 없이 표시.
// '전체'는 항상 노출.
function buildTabItems(dist: Record<string, number>, hasData: boolean, totalCount: number): AccentTabItem<ActiveTab>[] {
  const sourceTabs: AccentTabItem<ActiveTab>[] = [
    { value: 'confluence', label: 'Confluence', count: hasData ? (dist.confluence ?? 0) : undefined },
    { value: 'jira', label: 'Jira', count: hasData ? (dist.jira ?? 0) : undefined },
    { value: 'slack', label: 'Slack', count: hasData ? (dist.slack ?? 0) : undefined },
    { value: 'github', label: 'Github', count: hasData ? (dist.github ?? 0) : undefined },
    { value: 'channel_talk', label: '채널톡', count: hasData ? (dist.channel_talk ?? 0) : undefined },
  ];
  return [
    { value: 'all', label: '전체', count: hasData ? totalCount : undefined },
    ...(hasData ? sourceTabs.filter((tab) => (tab.count ?? 0) > 0) : sourceTabs),
  ];
}

export default function ResultPageHeader({
  keyword,
  toolFilters,
  draftKeyword,
  onDraftKeywordChange,
  draftChips,
  onDraftChipsChange,
  dateRange,
  draftDateRange,
  onDraftDateRangeChange,
  smartFilter,
  draftSmartFilter,
  onDraftSmartFilterChange,
  onSubmit,
  onHistorySubmit,
  onClear,
  onAiModeClick,
  activeTab,
  onTabChange,
  sortOrder,
  onSortChange,
}: ResultPageHeaderProps) {
  // ResultListSection과 같은 queryKey → cache 자동 공유, fetch 1회만.
  const { start, end } = dateRangeToUrlParams(dateRange);
  const query = useQuery(hybridSearchQueries.list({ keyword, toolFilters, start, end, smartFilter }));

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

  const tabItems = buildTabItems(distribution, query.data !== undefined, query.data?.results.length ?? 0);

  return (
    <header className="border-edge-normal flex w-full shrink-0 flex-col items-center border-b px-16 pt-5">
      <div className="flex w-full max-w-355 flex-col items-start gap-5">
        <ResultSearchBar
          value={draftKeyword}
          onValueChange={onDraftKeywordChange}
          chips={draftChips}
          onChipsChange={onDraftChipsChange}
          dateRange={draftDateRange}
          onDateRangeChange={onDraftDateRangeChange}
          smartFilter={smartFilter}
          draftSmartFilter={draftSmartFilter}
          onDraftSmartFilterChange={onDraftSmartFilterChange}
          onSubmit={onSubmit}
          onHistorySubmit={onHistorySubmit}
          onClear={onClear}
          onAiModeClick={onAiModeClick}
        />
        <div className="flex w-full items-center gap-5">
          <AccentTabs items={tabItems} value={activeTab} onValueChange={onTabChange} ariaLabel="결과 필터 탭" />
          <SortDropdown value={sortOrder} onChange={onSortChange} />
        </div>
      </div>
    </header>
  );
}
