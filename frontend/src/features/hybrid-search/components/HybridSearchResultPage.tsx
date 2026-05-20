'use client';

// /hybrid-search 컨테이너.
// URL: ?q (keyword) + ?tools (scope) 만 보존.
// active(drill-down 탭), page(페이지) 는 컴포넌트 state — fetch와 무관.
// keyword 또는 tools가 바뀌면 draft/active/page 모두 reset (prev-value 패턴).

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { motion } from 'motion/react';

import { motionEase, MotionState } from '@/shared/motion/presets';
import type { SortOrder } from '@/shared/utils/temporalRange';

import { useHybridSearchUrlState } from '../hooks/useHybridSearchUrlState';
import { type ActiveTab, TOOL_FILTERS_ARRAY, type ToolFilter } from '../types/hybridSearchApi';
import CatchupPromoCard from './CatchupPromoCard';
import ResultListSection from './ResultListSection';
import ResultPageBody from './ResultPageBody';
import ResultPageHeader from './ResultPageHeader';

// 라우트 진입 시 1회 짧은 fade. 페이지 내부 상태 전환은 ResultListSection 내부 AnimatePresence가 담당.
const pageEnter = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2, ease: motionEase } },
};

export default function HybridSearchResultPage() {
  const { keyword, tools, dateRange, commitSearch } = useHybridSearchUrlState();

  // draft state (input/chips/기간 임시 값) + UI state (active/page).
  const [draftKeyword, setDraftKeyword] = useState(keyword);
  const [draftChips, setDraftChips] = useState<ToolFilter[]>(tools);
  const [draftDateRange, setDraftDateRange] = useState<DateRange | undefined>(dateRange);
  const [active, setActive] = useState<ActiveTab>('all');
  const [page, setPage] = useState(1);
  const [sortOrder, setSortOrder] = useState<SortOrder>('relevance');

  // URL keyword/tools/기간 변경 시 모든 임시·UI state reset (render-phase prev-value).
  const [prevKeyword, setPrevKeyword] = useState(keyword);
  const toolsKey = tools.join(',');
  const [prevToolsKey, setPrevToolsKey] = useState(toolsKey);
  const rangeKey = `${dateRange?.from?.getTime() ?? ''}-${dateRange?.to?.getTime() ?? ''}`;
  const [prevRangeKey, setPrevRangeKey] = useState(rangeKey);
  if (prevKeyword !== keyword || prevToolsKey !== toolsKey || prevRangeKey !== rangeKey) {
    setPrevKeyword(keyword);
    setPrevToolsKey(toolsKey);
    setPrevRangeKey(rangeKey);
    setDraftKeyword(keyword);
    setDraftChips(tools);
    setDraftDateRange(dateRange);
    setActive('all');
    setPage(1);
  }

  // scope: chips 선택 있으면 그것, 없으면 5종 전체 fallback.
  const scope: ToolFilter[] = tools.length > 0 ? tools : TOOL_FILTERS_ARRAY;

  const handleSubmit = () => {
    commitSearch(draftKeyword, draftChips, draftDateRange);
  };

  // history 클릭도 submit과 동등한 commit: entry.query + draft chips/기간을 URL에 한 번에 반영.
  // ResultSearchBar가 onHistorySubmit 호출 후 input.blur() → expanded panel 자동 close.
  const handleHistorySubmit = (query: string) => {
    commitSearch(query, draftChips, draftDateRange);
  };

  // X 버튼: input draft만 비움. URL과 현재 표시 중인 검색 결과는 유지.
  // 사용자가 새 검색어 타이핑 후 submit해야 결과가 갱신됨.
  const handleClear = () => {
    setDraftKeyword('');
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
      className="bg-fill-normal flex min-h-full flex-col"
    >
      <ResultPageHeader
        keyword={keyword}
        scope={scope}
        draftKeyword={draftKeyword}
        onDraftKeywordChange={setDraftKeyword}
        draftChips={draftChips}
        onDraftChipsChange={setDraftChips}
        dateRange={dateRange}
        draftDateRange={draftDateRange}
        onDraftDateRangeChange={setDraftDateRange}
        onSubmit={handleSubmit}
        onHistorySubmit={handleHistorySubmit}
        onClear={handleClear}
        activeTab={active}
        onTabChange={handleTabChange}
        sortOrder={sortOrder}
        onSortChange={handleSortChange}
      />
      <ResultPageBody side={<CatchupPromoCard />}>
        <ResultListSection
          keyword={keyword}
          scope={scope}
          dateRange={dateRange}
          active={active}
          page={page}
          onPageChange={setPage}
          sortOrder={sortOrder}
        />
      </ResultPageBody>
    </motion.div>
  );
}
