'use client';

// 문서 탐색 모드(`?mode=docs`) 하단 검색 기록 섹션.
// 검색 기록 클릭 시 현재 선택된 chips(selectedSources)를 tools로 함께 push.
// 최근 탐색이 없으면 빈 상태를 렌더.

import type { DateRange } from 'react-day-picker';
import { useRouter } from 'next/navigation';

import SearchHistoryList from '@/shared/components/SearchHistoryList';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';
import type { DocsSource } from '@/shared/types/source';
import { dateRangeToUrlParams } from '@/shared/utils/temporalRange';

interface DocsSearchHistorySectionProps {
  selectedSources: DocsSource[];
  dateRange: DateRange | undefined;
  smartFilter: boolean;
}

export default function DocsSearchHistorySection({
  selectedSources,
  dateRange,
  smartFilter,
}: DocsSearchHistorySectionProps) {
  const router = useRouter();
  const { entries, isLoading } = useSearchHistoryEntries();

  const handleHistoryClick = (query: string) => {
    const params = new URLSearchParams({ q: query, smart_filter: String(smartFilter) });
    if (selectedSources.length > 0) {
      params.set('tools', selectedSources.join(','));
    }
    const { start, end } = dateRangeToUrlParams(dateRange);
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    router.push(`/hybrid-search?${params.toString()}`);
  };

  const isEmpty = !isLoading && entries.length === 0;

  return (
    <section className="flex w-full justify-center px-16 pb-30">
      <div className="custom-scrollbar bg-fill-normal-normal max-h-120 w-full max-w-190 overflow-y-auto rounded-3xl p-5">
        {isEmpty ? (
          <p className="text-body-xsmall text-text-normal-alternative w-full text-center">최근 탐색이 없습니다.</p>
        ) : (
          <SearchHistoryList
            entries={entries}
            isLoading={isLoading}
            onItemClick={(entry) => handleHistoryClick(entry.query)}
          />
        )}
      </div>
    </section>
  );
}
