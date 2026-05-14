'use client';

// Figma 11542:64433 — 결과 카드 리스트 + Pagination.
// backend는 dedup 후 최대 50개 한 번에 반환 → frontend가 active/page로 client-side filter+slice.

import Pagination from '@/shared/components/ui/pagination';
import { normalizeSources } from '@/shared/utils/normalize/normalizeRagSources';

import { useHybridSearch } from '../hooks/useHybridSearch';
import { HYBRID_SEARCH_PAGE_SIZE } from '../queries/hybridSearch.queries';
import type { ActiveTab, ToolFilter } from '../types/hybridSearchApi';
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
  const query = useHybridSearch({ keyword, scope });

  // active가 scope 밖이면 결과 없음 (사용자가 보지 못한 source 탭 클릭한 경우).
  const isActiveInScope = active === 'all' || scope.length === 0 || scope.includes(active);

  if (!keyword.trim()) return <ResultEmptyState />;
  if (query.isLoading) return <ResultLoadingState />;
  if (query.isError) return <ResultErrorState onRetry={() => query.refetch()} />;
  if (!isActiveInScope) return <ResultEmptyState />;
  if (!query.data || query.data.results.length === 0) return <ResultEmptyState />;

  // active filter (client-side) — active='all'이면 전체, 아니면 그 source만.
  const filteredResults =
    active === 'all'
      ? query.data.results
      : query.data.results.filter((r) => r.source === active);

  if (filteredResults.length === 0) return <ResultEmptyState />;

  // page slice (client-side, HYBRID_SEARCH_PAGE_SIZE = 10).
  const totalPages = Math.max(1, Math.ceil(filteredResults.length / HYBRID_SEARCH_PAGE_SIZE));
  const pageStart = (page - 1) * HYBRID_SEARCH_PAGE_SIZE;
  const pageResults = filteredResults.slice(pageStart, pageStart + HYBRID_SEARCH_PAGE_SIZE);
  const sources = normalizeSources(pageResults);

  return (
    <div className="flex w-full flex-col items-center gap-10">
      <div className="flex w-full flex-col items-start gap-2">
        {sources.map((source) => (
          <HybridSearchResultCard key={source.id} source={source} />
        ))}
      </div>
      {totalPages > 1 && (
        <Pagination currentPage={page} totalPages={totalPages} onPageChange={onPageChange} />
      )}
    </div>
  );
}
