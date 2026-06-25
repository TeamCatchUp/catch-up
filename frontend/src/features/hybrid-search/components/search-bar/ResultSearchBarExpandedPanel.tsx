'use client';

// ResultSearchBar의 expanded 시각 하단 영역.
// 상단: 문서 검색 필터 row. 하단: 검색 기록 + CatchupPromoCard.
// history click은 부모(ResultSearchBar)로 위임 — submit과 동일하게 처리되어 input blur + URL commit 한 번에.

import type { DateRange } from 'react-day-picker';

import DocumentSearchFilterRow from '@/shared/components/query/filter/DocumentSearchFilterRow';
import SearchHistoryList from '@/shared/components/SearchHistoryList';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';
import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import type { DocsSource } from '@/shared/types/source';

import CatchupPromoCard from './CatchupPromoCard';

interface ResultSearchBarExpandedPanelProps {
  selectedSources: DocsSource[];
  onSourcesToggle: (next: DocsSource[]) => void;
  dateRange: DateRange | undefined;
  onDateRangeChange: (next: DateRange | undefined) => void;
  smartFilter: boolean;
  onSmartFilterChange: (next: boolean) => void;
  onFilterOverlayOpenChange: (open: boolean) => void;
  onHistoryItemClick: (query: string) => void;
  historyEntries?: SearchHistoryEntry[];
  historyLoading?: boolean;
}

export default function ResultSearchBarExpandedPanel({
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
}: ResultSearchBarExpandedPanelProps) {
  const shouldUseHistoryFixture = historyEntries !== undefined;
  const { entries: queriedHistory, isLoading: isQueriedHistoryLoading } = useSearchHistoryEntries({
    enabled: !shouldUseHistoryFixture,
  });
  const history = historyEntries ?? queriedHistory;
  const isHistoryLoading = historyLoading ?? isQueriedHistoryLoading;

  // onMouseDown preventDefault: 패널 내부 어떤 요소 클릭해도 input focus가 유지됨
  // (chips, history item 등이 focus를 가져가 onBlur로 패널이 닫히는 문제 방지).
  return (
    <div
      className="animate-in fade-in-0 slide-in-from-top-3 flex min-h-0 w-full flex-1 flex-col gap-3 duration-300"
      onMouseDown={(e) => e.preventDefault()}
    >
      <DocumentSearchFilterRow
        className="w-[calc(100%+2px)]"
        variant="result-expanded"
        selectedSources={selectedSources}
        onSourcesChange={onSourcesToggle}
        dateRange={dateRange}
        onDateRangeChange={onDateRangeChange}
        smartFilter={smartFilter}
        onSmartFilterChange={onSmartFilterChange}
        preserveInputFocus
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
