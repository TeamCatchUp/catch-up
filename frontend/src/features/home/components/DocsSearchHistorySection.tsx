'use client';

// 문서 탐색 모드(`?mode=docs`) 컴포저 아래 검색 기록 섹션.
// 기록을 클릭하면 현재 필터를 그대로 실어 결과 페이지로 넘어간다.

import type { DateRange } from 'react-day-picker';
import { useRouter } from 'next/navigation';

import SearchHistoryList from '@/shared/components/SearchHistoryList';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';
import type { DocsSource } from '@/shared/types/source';
import { buildHybridSearchUrl } from '@/shared/utils/buildHybridSearchUrl';

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
    const url = buildHybridSearchUrl({ query, sources: selectedSources, dateRange, smartFilter });
    if (url) router.push(url);
  };

  const isEmpty = !isLoading && entries.length === 0;

  return (
    <section className="custom-scrollbar bg-fill-normal-normal max-h-120 w-full overflow-y-auto rounded-3xl p-5">
      {isEmpty ? (
        <p className="text-body-xsmall text-text-normal-alternative w-full text-center">최근 탐색이 없습니다.</p>
      ) : (
        <SearchHistoryList
          entries={entries}
          isLoading={isLoading}
          onItemClick={(entry) => handleHistoryClick(entry.query)}
        />
      )}
    </section>
  );
}
