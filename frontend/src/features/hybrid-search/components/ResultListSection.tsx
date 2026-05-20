'use client';

// 결과 카드 리스트 + Pagination.
// backend는 dedup 후 최대 50개 한 번에 반환 → frontend가 active/page로 client-side filter+slice.

import type { DateRange } from 'react-day-picker';
import { AnimatePresence, motion } from 'motion/react';

import Pagination from '@/shared/components/ui/pagination';
import { motionEase, MotionState } from '@/shared/motion/presets';
import { normalizeSources } from '@/shared/utils/normalize/normalizeRagSources';
import { dateRangeToUrlParams, sortByRelevance, sortByUpdatedAt, type SortOrder } from '@/shared/utils/temporalRange';

import { useHybridSearch } from '../hooks/useHybridSearch';
import { HYBRID_SEARCH_PAGE_SIZE } from '../queries/hybridSearch.queries';
import type { ActiveTab, ToolFilter } from '../types/hybridSearchApi';
import HybridSearchResultCard from './HybridSearchResultCard';
import ResultEmptyState from './ResultEmptyState';
import ResultErrorState from './ResultErrorState';
import ResultLoadingState from './ResultLoadingState';
import SearchPeriodLabel from './SearchPeriodLabel';

// hybrid-search 결과 리스트 전용 fast variants (source panel보다 빠르게).
const fastStaggerContainer = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05, delayChildren: 0.02 },
  },
};

const fastFadeInUp = {
  hidden: { opacity: 0, y: 4 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease: motionEase },
  },
};

// state 간 crossfade (Loading/Empty/Error/Results 사이).
const stateCrossfade = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2, ease: motionEase } },
  exit: { opacity: 0, transition: { duration: 0.15, ease: motionEase } },
};

interface ResultListSectionProps {
  keyword: string;
  scope: ToolFilter[];
  dateRange: DateRange | undefined;
  sortOrder: SortOrder;
  active: ActiveTab;
  page: number;
  onPageChange: (next: number) => void;
}

type ViewState = 'empty' | 'loading' | 'error' | 'results';

export default function ResultListSection({
  keyword,
  scope,
  dateRange,
  sortOrder,
  active,
  page,
  onPageChange,
}: ResultListSectionProps) {
  const { start, end } = dateRangeToUrlParams(dateRange);
  const query = useHybridSearch({ keyword, scope, start, end });

  // active가 scope 밖이면 결과 없음 (사용자가 보지 못한 source 탭 클릭한 경우).
  const isActiveInScope = active === 'all' || scope.length === 0 || scope.includes(active);

  let view: ViewState;
  let resultsData: {
    sources: ReturnType<typeof normalizeSources>;
    totalPages: number;
    transitionKey: string;
  } | null = null;

  if (!keyword.trim()) {
    view = 'empty';
  } else if (query.isLoading) {
    view = 'loading';
  } else if (query.isError) {
    view = 'error';
  } else if (!isActiveInScope || !query.data || query.data.results.length === 0) {
    view = 'empty';
  } else {
    const filteredResults =
      active === 'all'
        ? query.data.results
        : query.data.results.filter((r) => r.source === active);
    if (filteredResults.length === 0) {
      view = 'empty';
    } else {
      const sortedResults =
        sortOrder === 'relevance'
          ? sortByRelevance(filteredResults)
          : sortByUpdatedAt(filteredResults, sortOrder);
      const totalPages = Math.max(1, Math.ceil(sortedResults.length / HYBRID_SEARCH_PAGE_SIZE));
      const pageStart = (page - 1) * HYBRID_SEARCH_PAGE_SIZE;
      const pageResults = sortedResults.slice(pageStart, pageStart + HYBRID_SEARCH_PAGE_SIZE);
      resultsData = {
        sources: normalizeSources(pageResults),
        totalPages,
        transitionKey: `${keyword}-${scope.join(',')}-${active}-${sortOrder}-${page}`,
      };
      view = 'results';
    }
  }

  return (
    <AnimatePresence mode="wait">
      {view === 'loading' && <ResultLoadingState key="loading" />}
      {view === 'error' && (
        <ResultErrorState key="error" onRetry={() => query.refetch()} />
      )}
      {view === 'empty' && <ResultEmptyState key="empty" />}
      {view === 'results' && resultsData && (
        <motion.div
          key="results"
          initial={MotionState.Hidden}
          animate={MotionState.Visible}
          exit={MotionState.Exit}
          variants={stateCrossfade}
          className="flex w-full flex-col items-center gap-10"
        >
          <motion.div
            key={resultsData.transitionKey}
            initial={MotionState.Hidden}
            animate={MotionState.Visible}
            variants={fastStaggerContainer}
            className="flex w-full flex-col items-start gap-2"
          >
            {dateRange?.from && <SearchPeriodLabel dateRange={dateRange} />}
            {resultsData.sources.map((source) => (
              <motion.div key={source.id} variants={fastFadeInUp} className="w-full">
                <HybridSearchResultCard source={source} />
              </motion.div>
            ))}
          </motion.div>
          {resultsData.totalPages > 1 && (
            <Pagination
              currentPage={page}
              totalPages={resultsData.totalPages}
              onPageChange={onPageChange}
            />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
