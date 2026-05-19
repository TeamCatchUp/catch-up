'use client';

// 문서 탐색 모드(`?mode=docs`) 하단 검색 기록 섹션.
// 검색 기록 클릭 시 현재 선택된 chips(selectedSources)를 tools로 함께 push.
// 최근 탐색이 없으면 빈 상태(Figma 13630:62641)를 렌더.

import { useRouter } from 'next/navigation';

import SearchHistoryList from '@/shared/components/SearchHistoryList';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';
import type { DocsSource } from '@/shared/types/source';

interface DocsSearchHistorySectionProps {
  selectedSources: DocsSource[];
}

export default function DocsSearchHistorySection({ selectedSources }: DocsSearchHistorySectionProps) {
  const router = useRouter();
  const { entries, isLoading } = useSearchHistoryEntries();

  const handleHistoryClick = (query: string) => {
    const params = new URLSearchParams({ q: query });
    if (selectedSources.length > 0) {
      params.set('tools', selectedSources.join(','));
    }
    router.push(`/hybrid-search?${params.toString()}`);
  };

  const isEmpty = !isLoading && entries.length === 0;

  return (
    <section className="flex w-full justify-center px-16 pb-30">
      <div className="custom-scrollbar bg-fill-normal max-h-120 w-full max-w-190 overflow-y-auto rounded-3xl p-5">
        {isEmpty ? (
          <p className="text-body-xsmall text-content-alternative w-full text-center">
            최근 탐색이 없습니다.
          </p>
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
