'use client';

// 문서 탐색 모드(`?mode=docs`) 하단 검색 기록 섹션.
// 검색 기록 클릭 시 현재 선택된 chips(selectedSources)를 tools로 함께 push.

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

  return (
    <section className="flex w-full justify-center px-16 pb-30">
      <div className="bg-fill-normal flex w-full max-w-190 flex-col gap-5 rounded-3xl p-5">
        <SearchHistoryList
          entries={entries}
          isLoading={isLoading}
          maxPerGroup={3}
          onItemClick={(entry) => handleHistoryClick(entry.query)}
        />
      </div>
    </section>
  );
}
