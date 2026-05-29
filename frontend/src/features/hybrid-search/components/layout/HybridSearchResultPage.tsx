'use client';

// /hybrid-search 컨테이너.
// URL: ?q (keyword) + ?tools (scope) 만 보존.
// active(drill-down 탭), page(페이지) 는 컴포넌트 state — fetch와 무관.
// keyword 또는 tools가 바뀌면 draft/active/page 모두 reset (prev-value 패턴).

import { useMemo, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { motion } from 'motion/react';
import { useRouter } from 'next/navigation';

import { motionEase, MotionState } from '@/shared/motion/presets';
import type { RagSourceUiModel } from '@/shared/types/ragSourceModel';
import type { SourceResponseApi } from '@/shared/types/sourceApi';
import { normalizeSources } from '@/shared/utils/normalize/normalizeRagSources';
import { dateRangeToUrlParams, type SortOrder } from '@/shared/utils/temporalRange';

import { useHybridSearch } from '../../hooks/useHybridSearch';
import { useHybridSearchUrlState } from '../../hooks/useHybridSearchUrlState';
import { type ActiveTab, TOOL_FILTERS_ARRAY, type ToolFilter } from '../../types/hybridSearchApi';
import OriginalPanel from '../original/OriginalPanel';
import ResultListSection from '../result-list/ResultListSection';
import ResultPageBody from './ResultPageBody';
import ResultPageHeader from './ResultPageHeader';

// 라우트 진입 시 1회 짧은 fade. 페이지 내부 상태 전환은 ResultListSection 내부 AnimatePresence가 담당.
const pageEnter = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2, ease: motionEase } },
};

export default function HybridSearchResultPage() {
  const router = useRouter();
  const { keyword, tools, smartFilter, dateRange, commitSearch } = useHybridSearchUrlState();

  // draft state (input/chips/기간 임시 값) + UI state (active/page).
  const [draftKeyword, setDraftKeyword] = useState(keyword);
  const [draftChips, setDraftChips] = useState<ToolFilter[]>(tools);
  const [draftDateRange, setDraftDateRange] = useState<DateRange | undefined>(dateRange);
  const [active, setActive] = useState<ActiveTab>('all');
  const [page, setPage] = useState(1);
  const [sortOrder, setSortOrder] = useState<SortOrder>('relevance');

  // 우측 원문 패널이 보여줄 선택 소스. 미선택이면 첫 결과로 자동 폴백.
  const [selectedSource, setSelectedSource] = useState<SourceResponseApi | null>(null);

  // URL keyword/tools/기간 변경 시 입력 draft reset. smart filter만 바뀐 경우 draft 입력은 보존한다.
  const [prevKeyword, setPrevKeyword] = useState(keyword);
  const toolsKey = tools.join(',');
  const [prevToolsKey, setPrevToolsKey] = useState(toolsKey);
  const rangeKey = `${dateRange?.from?.getTime() ?? ''}-${dateRange?.to?.getTime() ?? ''}`;
  const [prevRangeKey, setPrevRangeKey] = useState(rangeKey);
  const [prevSmartFilter, setPrevSmartFilter] = useState(smartFilter);
  if (prevKeyword !== keyword || prevToolsKey !== toolsKey || prevRangeKey !== rangeKey) {
    setPrevKeyword(keyword);
    setPrevToolsKey(toolsKey);
    setPrevRangeKey(rangeKey);
    setDraftKeyword(keyword);
    setDraftChips(tools);
    setDraftDateRange(dateRange);
    setActive('all');
    setPage(1);
    setSelectedSource(null);
  }
  if (prevSmartFilter !== smartFilter) {
    setPrevSmartFilter(smartFilter);
    setActive('all');
    setPage(1);
    setSelectedSource(null);
  }

  // displayScope: 탭/결과 화면 표시용 fallback. API에는 수동 tools만 별도로 전달한다.
  const displayScope: ToolFilter[] = tools.length > 0 ? tools : TOOL_FILTERS_ARRAY;

  // ResultListSection과 동일한 파생 — 쿼리키 일치로 캐시 공유(추가 fetch 0).
  const { start, end } = dateRangeToUrlParams(dateRange);
  const query = useHybridSearch({ keyword, toolFilters: tools, start, end, smartFilter });
  const results = useMemo(() => query.data?.results ?? [], [query.data]);

  // 카드는 RagSourceUiModel만 들고 있어 원본 SourceResponseApi 역해석이 필요.
  // normalizeSources 결과와 원본 results를 zip해 id → 원본 Map 구성.
  const sourceById = useMemo(() => {
    const map = new Map<string, SourceResponseApi>();
    normalizeSources(results).forEach((uiSource, index) => {
      const raw = results[index];
      if (raw) map.set(uiSource.id, raw);
    });
    return map;
  }, [results]);

  // 자동 선택: 명시 선택 없으면 첫 결과. 첫 결과가 user_chat이 아니면 패널은 Coming Soon.
  const effectiveSource = selectedSource ?? results[0] ?? null;

  const handleSelectSource = (uiSource: RagSourceUiModel) => {
    const raw = sourceById.get(uiSource.id);
    if (raw) setSelectedSource(raw);
  };

  const handleSubmit = () => {
    commitSearch(draftKeyword, draftChips, draftDateRange, smartFilter);
  };

  // history 클릭도 submit과 동등한 commit: entry.query + draft chips/기간을 URL에 한 번에 반영.
  // ResultSearchBar가 onHistorySubmit 호출 후 input.blur() → expanded panel 자동 close.
  const handleHistorySubmit = (query: string) => {
    commitSearch(query, draftChips, draftDateRange, smartFilter);
  };

  const handleSmartFilterChange = (next: boolean) => {
    commitSearch(keyword, tools, dateRange, next);
  };

  // X 버튼: input draft만 비움. URL과 현재 표시 중인 검색 결과는 유지.
  // 사용자가 새 검색어 타이핑 후 submit해야 결과가 갱신됨.
  const handleClear = () => {
    setDraftKeyword('');
  };

  const handleAiModeClick = () => {
    const trimmed = draftKeyword.trim();
    if (!trimmed) {
      router.push('/search');
      return;
    }
    const params = new URLSearchParams({ q: trimmed });
    router.push(`/search?${params.toString()}`);
  };

  // 탭 변경 시 페이지도 1로 reset.
  const handleTabChange = (next: ActiveTab) => {
    setActive(next);
    setPage(1);
  };

  // 정렬 변경 시 페이지도 1로 reset.
  const handleSortChange = (next: SortOrder) => {
    setSortOrder(next);
    setPage(1);
  };

  return (
    <motion.div
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      variants={pageEnter}
      className="bg-fill-normal flex h-dvh min-h-0 flex-col overflow-hidden"
    >
      <ResultPageHeader
        keyword={keyword}
        toolFilters={tools}
        draftKeyword={draftKeyword}
        onDraftKeywordChange={setDraftKeyword}
        draftChips={draftChips}
        onDraftChipsChange={setDraftChips}
        dateRange={dateRange}
        draftDateRange={draftDateRange}
        onDraftDateRangeChange={setDraftDateRange}
        smartFilter={smartFilter}
        onSmartFilterChange={handleSmartFilterChange}
        onSubmit={handleSubmit}
        onHistorySubmit={handleHistorySubmit}
        onClear={handleClear}
        onAiModeClick={handleAiModeClick}
        activeTab={active}
        onTabChange={handleTabChange}
        sortOrder={sortOrder}
        onSortChange={handleSortChange}
      />
      <ResultPageBody
        side={
          <OriginalPanel
            connector={effectiveSource?.source ?? null}
            entityType={effectiveSource?.entity_type ?? null}
            documentId={effectiveSource?.id ?? null}
          />
        }
      >
        <ResultListSection
          keyword={keyword}
          scope={displayScope}
          tools={tools}
          dateRange={dateRange}
          smartFilter={smartFilter}
          active={active}
          page={page}
          onPageChange={setPage}
          sortOrder={sortOrder}
          selectedId={effectiveSource?.id ?? null}
          onSelectSource={handleSelectSource}
        />
      </ResultPageBody>
    </motion.div>
  );
}
