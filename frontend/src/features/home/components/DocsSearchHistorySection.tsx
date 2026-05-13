'use client';

// 문서 탐색 모드(`?mode=docs`) 하단 검색 기록 섹션.
// 상단 섹션과 gap/padding 없이 별도 section으로 분리.

import { useRouter } from 'next/navigation';

import SearchHistoryList from '@/shared/components/SearchHistoryList';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';

export default function DocsSearchHistorySection() {
  const router = useRouter();
  const { entries, isLoading } = useSearchHistoryEntries();

  return (
    <section className="flex w-full justify-center px-16 pb-30">
      <div className="bg-fill-normal flex w-full max-w-190 flex-col gap-5 rounded-3xl p-5">
        <SearchHistoryList
          entries={entries}
          isLoading={isLoading}
          maxPerGroup={3}
          onItemClick={(entry) => router.push(`/hybrid-search?q=${encodeURIComponent(entry.query)}`)}
        />
      </div>
    </section>
  );
}
