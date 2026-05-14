'use client';

// ResultSearchBar의 expanded 시각 하단 영역.
// 좌측: SourceChipsRow + 검색 기록, 우측: CatchupPromoCard.
// Figma 13426:52888 — chips 위, 그 아래 좌측 history(flex-1) + 우측 promo(w-80).

import { useRouter } from 'next/navigation';

import SearchHistoryList from '@/shared/components/SearchHistoryList';
import SourceChipsRow from '@/shared/components/SourceChipsRow';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';
import type { DocsSource } from '@/shared/types/source';

import CatchupPromoCard from './CatchupPromoCard';

interface ResultSearchBarExpandedPanelProps {
  selectedSources: DocsSource[];
  onSourcesToggle: (next: DocsSource[]) => void;
}

export default function ResultSearchBarExpandedPanel({
  selectedSources,
  onSourcesToggle,
}: ResultSearchBarExpandedPanelProps) {
  const router = useRouter();
  const { entries: history, isLoading: isHistoryLoading } = useSearchHistoryEntries();

  return (
    <div className="animate-in fade-in-0 slide-in-from-top-3 flex w-full flex-col gap-2.5 duration-300">
      <SourceChipsRow
        className="w-full justify-start"
        selectedSources={selectedSources}
        onToggle={onSourcesToggle}
      />
      <div className="flex w-full flex-1 items-start gap-6">
        <div className="min-w-0 flex-1">
          <SearchHistoryList
            entries={history}
            isLoading={isHistoryLoading}
            maxPerGroup={3}
            onItemClick={(entry) => router.push(`/hybrid-search?q=${encodeURIComponent(entry.query)}`)}
          />
        </div>
        <div className="w-80 shrink-0">
          <CatchupPromoCard />
        </div>
      </div>
    </div>
  );
}
