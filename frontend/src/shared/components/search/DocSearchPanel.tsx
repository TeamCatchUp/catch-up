'use client';

// 문서 검색 입력 아래에 붙는 본문 — 필터 행 + 검색 기록 + 프로모 카드 2단.
// preserveInputFocus는 입력 포커스를 잃으면 닫히는 소비처(결과 페이지 검색바)를 위한 것이다.

import type { DateRange } from 'react-day-picker';

import DocumentSearchFilterRow from '@/shared/components/query/filter/DocumentSearchFilterRow';
import SearchHistoryList from '@/shared/components/SearchHistoryList';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';
import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';

import CatchupPromoCard from './CatchupPromoCard';

interface DocSearchPanelProps {
  selectedSources: DocsSource[];
  onSourcesToggle: (next: DocsSource[]) => void;
  dateRange: DateRange | undefined;
  onDateRangeChange: (next: DateRange | undefined) => void;
  smartFilter: boolean;
  onSmartFilterChange: (next: boolean) => void;
  onFilterOverlayOpenChange?: (open: boolean) => void;
  onHistoryItemClick: (query: string) => void;
  historyEntries?: SearchHistoryEntry[];
  historyLoading?: boolean;
  preserveInputFocus?: boolean;
  className?: string;
  filterRowClassName?: string;
}

export default function DocSearchPanel({
  selectedSources,
  onSourcesToggle,
  dateRange,
  onDateRangeChange,
  smartFilter,
  onSmartFilterChange,
  onFilterOverlayOpenChange,
  onHistoryItemClick,
  historyEntries,
  historyLoading,
  preserveInputFocus = false,
  className,
  filterRowClassName,
}: DocSearchPanelProps) {
  const shouldUseHistoryFixture = historyEntries !== undefined;
  const { entries: queriedHistory, isLoading: isQueriedHistoryLoading } = useSearchHistoryEntries({
    enabled: !shouldUseHistoryFixture,
  });
  const history = historyEntries ?? queriedHistory;
  const isHistoryLoading = historyLoading ?? isQueriedHistoryLoading;

  return (
    <div
      className={cn('flex min-h-0 w-full flex-1 flex-col gap-3', className)}
      onMouseDown={preserveInputFocus ? (e) => e.preventDefault() : undefined}
    >
      <DocumentSearchFilterRow
        className={filterRowClassName}
        variant="result-expanded"
        selectedSources={selectedSources}
        onSourcesChange={onSourcesToggle}
        dateRange={dateRange}
        onDateRangeChange={onDateRangeChange}
        smartFilter={smartFilter}
        onSmartFilterChange={onSmartFilterChange}
        preserveInputFocus={preserveInputFocus}
        onFilterOverlayOpenChange={onFilterOverlayOpenChange}
      />
      <div className="flex min-h-0 w-full flex-1 items-start gap-6 overflow-hidden">
        <div className="custom-scrollbar min-h-0 min-w-0 flex-1 overflow-y-auto pr-5">
          <SearchHistoryList
            entries={history}
            isLoading={isHistoryLoading}
            onItemClick={(entry) => onHistoryItemClick(entry.query)}
          />
        </div>
        <div className="mr-6 h-full w-80 shrink-0">
          <CatchupPromoCard />
        </div>
      </div>
    </div>
  );
}
