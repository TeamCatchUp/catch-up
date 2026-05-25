'use client';

// 결과 카드 리스트 + Pagination.
// backend는 dedup 후 최대 50개 한 번에 반환 → frontend가 active/page로 client-side filter+slice.

import type { DateRange } from 'react-day-picker';
import { AnimatePresence, motion } from 'motion/react';

import Pagination from '@/shared/components/ui/pagination';
import { motionEase, MotionState } from '@/shared/motion/presets';
import type { RagSourceUiModel } from '@/shared/types/ragSourceModel';
import { applySlackDateFallback } from '@/shared/utils/normalize/applySlackDateFallback';
import { normalizeSources } from '@/shared/utils/normalize/normalizeRagSources';
import { dateRangeToUrlParams, sortByRelevance, sortByUpdatedAt, type SortOrder } from '@/shared/utils/temporalRange';

import { useHybridSearch } from '../../hooks/useHybridSearch';
import { HYBRID_SEARCH_PAGE_SIZE } from '../../queries/hybridSearch.queries';
import type { ActiveTab, ToolFilter } from '../../types/hybridSearchApi';
import ResultEmptyState from '../result-states/ResultEmptyState';
import ResultErrorState from '../result-states/ResultErrorState';
import ResultLoadingState from '../result-states/ResultLoadingState';
import HybridSearchResultCard from './HybridSearchResultCard';
import SearchPeriodLabel from './SearchPeriodLabel';
import SearchToolLabel from './SearchToolLabel';

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
  // URL ?tools= 의 raw 값 — 빈 배열이면 필터 미적용(SearchToolLabel 렌더 안 됨).
  // scope 는 빈 배열일 때 5종 fallback 이 적용된 값이라 라벨 표시용으로 부적절.
  tools?: ToolFilter[];
  dateRange: DateRange | undefined;
  sortOrder: SortOrder;
  active: ActiveTab;
  page: number;
  onPageChange: (next: number) => void;
  selectedId: string | null;
  onSelectSource: (source: RagSourceUiModel) => void;
}

type ViewState = 'empty' | 'loading' | 'error' | 'results';

export default function ResultListSection({
  keyword,
  scope,
  tools = [],
  dateRange,
  sortOrder,
  active,
  page,
  onPageChange,
  selectedId,
  onSelectSource,
}: ResultListSectionProps) {
  const { start, end } = dateRangeToUrlParams(dateRange);
  const query = useHybridSearch({ keyword, scope, start, end });
  const hasSearchFilterLabel = Boolean(dateRange?.from) || tools.length > 0;

  // active가 scope 밖이면 결과 없음 (사용자가 보지 못한 source 탭 클릭한 경우).
  const isActiveInScope = active === 'all' || scope.length === 0 || scope.includes(active);

  let view: ViewState;
  let resultsData: {
    sources: ReturnType<typeof normalizeSources>;
    totalPages: number;
    totalCount: number;
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
      active === 'all' ? query.data.results : query.data.results.filter((r) => r.source === active);
    if (filteredResults.length === 0) {
      view = 'empty';
    } else {
      // Slack은 ingestion 단에서 미편집 메시지의 updated_at을 채우지 않음 → created_at으로 폴백 후 정렬·표시.
      const itemsWithDateFallback = applySlackDateFallback(filteredResults);
      const sortedResults =
        sortOrder === 'relevance'
          ? sortByRelevance(itemsWithDateFallback)
          : sortByUpdatedAt(itemsWithDateFallback, sortOrder);
      const totalPages = Math.max(1, Math.ceil(sortedResults.length / HYBRID_SEARCH_PAGE_SIZE));
      const pageStart = (page - 1) * HYBRID_SEARCH_PAGE_SIZE;
      const pageResults = sortedResults.slice(pageStart, pageStart + HYBRID_SEARCH_PAGE_SIZE);
      resultsData = {
        sources: normalizeSources(pageResults),
        totalPages,
        totalCount: sortedResults.length,
        transitionKey: `${keyword}-${scope.join(',')}-${active}-${sortOrder}-${page}`,
      };
      view = 'results';
    }
  }

  return (
    <AnimatePresence mode="wait">
      {view === 'loading' && <ResultLoadingState key="loading" />}
      {view === 'error' && <ResultErrorState key="error" onRetry={() => query.refetch()} />}
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
            className="flex w-full flex-col items-start"
          >
            {/* bg Fill/Normal/Strong + 1000px pill 컨테이너. 카드 첫 번째와 mb-1.5 (6px) gap. */}
            {hasSearchFilterLabel && (
              <div className="bg-fill-strong mb-1.5 flex w-full items-center justify-between rounded-full px-1.5 py-1">
                <div className="flex items-center gap-2.5">
                  {dateRange?.from && <SearchPeriodLabel dateRange={dateRange} />}
                  {dateRange?.from && tools.length > 0 && (
                    <span aria-hidden className="bg-dim-black-25 h-3 w-px shrink-0" />
                  )}
                  {tools.length > 0 && <SearchToolLabel tools={tools} />}
                </div>
                <span className="text-body-xsmall text-content-assistive shrink-0 px-2.5">
                  {resultsData.totalCount}건의 검색 결과
                </span>
              </div>
            )}
            {resultsData.sources.map((source) => (
              <motion.div key={source.id} variants={fastFadeInUp} className="w-full">
                <HybridSearchResultCard
                  source={source}
                  isSelected={source.id === selectedId}
                  onSelect={onSelectSource}
                />
              </motion.div>
            ))}
          </motion.div>
          {resultsData.totalPages > 1 && (
            <Pagination currentPage={page} totalPages={resultsData.totalPages} onPageChange={onPageChange} />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
