'use client';

// Figma 11542:64433 — 결과 카드 리스트 + Pagination.
// 외부: flex flex-col gap-10(40px) items-center
// 카드 리스트: flex flex-col gap-2(8px) min-w-[534px] w-full

import Pagination from '@/shared/components/ui/pagination';

import { useHybridSearch } from '../hooks/useHybridSearch';
import type { ActiveTab } from '../hooks/useHybridSearchUrlState';
import { HYBRID_SEARCH_PAGE_SIZE } from '../queries/hybridSearch.queries';
import type { ToolFilter } from '../types/hybridSearchApi';
import { mapHybridSearchResult } from '../utils/mapHybridSearchResult';
import HybridSearchResultCard from './HybridSearchResultCard';
import ResultEmptyState from './ResultEmptyState';
import ResultErrorState from './ResultErrorState';
import ResultLoadingState from './ResultLoadingState';

interface ResultListSectionProps {
  keyword: string;
  scope: ToolFilter[];
  active: ActiveTab;
  page: number;
  onPageChange: (next: number) => void;
}

export default function ResultListSection({
  keyword,
  scope,
  active,
  page,
  onPageChange,
}: ResultListSectionProps) {
  const query = useHybridSearch({ keyword, scope, active, page });

  // keyword 빈 문자열 → Empty (enabled=false라 fetch 안 함)
  if (!keyword.trim()) return <ResultEmptyState />;
  // scope 밖 active 탭 클릭 → API 호출 없이 EmptyState
  if (query.isOutOfScope) return <ResultEmptyState />;
  if (query.isLoading) return <ResultLoadingState />;
  if (query.isError) return <ResultErrorState onRetry={() => query.refetch()} />;
  if (!query.data || query.data.results.length === 0) return <ResultEmptyState />;

  const totalPages = Math.max(1, Math.ceil(query.data.total / HYBRID_SEARCH_PAGE_SIZE));
  const cards = query.data.results.map(mapHybridSearchResult);

  return (
    <div className="flex w-full flex-col items-center gap-10">
      <div className="flex w-full flex-col items-start gap-2">
        {cards.map((card) => {
          const { id, ...rest } = card;
          return <HybridSearchResultCard key={id} {...rest} />;
        })}
      </div>
      {totalPages > 1 && (
        <Pagination currentPage={page} totalPages={totalPages} onPageChange={onPageChange} />
      )}
    </div>
  );
}
