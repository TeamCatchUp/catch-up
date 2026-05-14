'use client';

// ResultSearchBar의 expanded 시각 하단 영역.
// 좌측: SourceChipsRow + 검색 기록, 우측: CatchupPromoCard.
// Figma 13426:52888 — chips 위, 그 아래 좌측 history(flex-1) + 우측 promo(w-80).
// 검색 기록 클릭 시 현재 URL의 tools 유지 (사용자 의도된 scope 보존).

import { useRouter } from 'next/navigation';

import SearchHistoryList from '@/shared/components/SearchHistoryList';
import SourceChipsRow from '@/shared/components/SourceChipsRow';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';
import type { DocsSource } from '@/shared/types/source';

import { useHybridSearchUrlState } from '../hooks/useHybridSearchUrlState';
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
  const { tools: currentUrlTools } = useHybridSearchUrlState();
  const { entries: history, isLoading: isHistoryLoading } = useSearchHistoryEntries();

  const handleHistoryClick = (query: string) => {
    const params = new URLSearchParams({ q: query });
    if (currentUrlTools.length > 0) {
      params.set('tools', currentUrlTools.join(','));
    }
    router.push(`/hybrid-search?${params.toString()}`);
  };

  // onMouseDown preventDefault: 패널 내부 어떤 요소 클릭해도 input focus가 유지됨
  // (chips, history item 등이 focus를 가져가 onBlur로 패널이 닫히는 문제 방지).
  return (
    <div
      className="animate-in fade-in-0 slide-in-from-top-3 flex w-full flex-col gap-2.5 duration-300"
      onMouseDown={(e) => e.preventDefault()}
    >
      <SourceChipsRow
        className="w-full justify-start"
        selectedSources={selectedSources}
        onToggle={onSourcesToggle}
      />
      <div className="flex w-full flex-1 items-start gap-6">
        <div className="min-w-0 max-h-95 flex-1 overflow-y-auto">
          <SearchHistoryList
            entries={history}
            isLoading={isHistoryLoading}
            onItemClick={(entry) => handleHistoryClick(entry.query)}
          />
        </div>
        <div className="w-80 shrink-0">
          <CatchupPromoCard />
        </div>
      </div>
    </div>
  );
}
