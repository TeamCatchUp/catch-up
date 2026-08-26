'use client';

// ResultSearchBar의 expanded 하단 영역. 본문은 shared DocSearchPanel이고 여기서는 결과 페이지용 폭·모션만 얹는다.
// history click은 부모로 위임 — submit과 동일하게 input blur + URL commit이 한 번에 일어난다.

import type { DateRange } from 'react-day-picker';

import DocSearchPanel from '@/shared/components/search/DocSearchPanel';
import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import type { DocsSource } from '@/shared/types/source';

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

export default function ResultSearchBarExpandedPanel(props: ResultSearchBarExpandedPanelProps) {
  return (
    <DocSearchPanel
      {...props}
      preserveInputFocus
      className="animate-in fade-in-0 slide-in-from-top-3 duration-300"
      filterRowClassName="w-[calc(100%+2px)]"
    />
  );
}
