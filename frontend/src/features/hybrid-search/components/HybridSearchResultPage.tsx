'use client';

// /hybrid-search 컨테이너.
// URL `tools`(scope, immutable) + `active`(drill-down) 분리.
// scope = tools 있으면 그것, 없으면 5종 전체 fallback.

import { useState } from 'react';

import { type ActiveTab,useHybridSearchUrlState } from '../hooks/useHybridSearchUrlState';
import { TOOL_FILTERS_ARRAY, type ToolFilter } from '../types/hybridSearchApi';
import CatchupPromoCard from './CatchupPromoCard';
import ResultListSection from './ResultListSection';
import ResultPageBody from './ResultPageBody';
import ResultPageHeader from './ResultPageHeader';

export default function HybridSearchResultPage() {
  const { keyword, tools, active, page, setKeyword, setActive, setPage } = useHybridSearchUrlState();

  // URL keyword 변경 시 draftKeyword 동기 reset — render-phase prev-value 패턴.
  const [draftKeyword, setDraftKeyword] = useState(keyword);
  const [prevKeyword, setPrevKeyword] = useState(keyword);
  if (prevKeyword !== keyword) {
    setPrevKeyword(keyword);
    setDraftKeyword(keyword);
  }

  // scope: chips 선택 있으면 그것, 없으면 5종 전체.
  const scope: ToolFilter[] = tools.length > 0 ? tools : TOOL_FILTERS_ARRAY;

  const handleSubmit = () => {
    setKeyword(draftKeyword);
  };

  const handleClear = () => {
    setDraftKeyword('');
    setKeyword('');
  };

  // '전체' → active='all' (URL에서 active 제거), source → active=그 source.
  const handleTabChange = (next: ActiveTab) => {
    setActive(next);
  };

  return (
    <div className="bg-fill-normal flex min-h-full flex-col">
      <ResultPageHeader
        keyword={keyword}
        scope={scope}
        draftKeyword={draftKeyword}
        onDraftKeywordChange={setDraftKeyword}
        onSubmit={handleSubmit}
        onClear={handleClear}
        activeTab={active}
        onTabChange={handleTabChange}
      />
      <ResultPageBody side={<CatchupPromoCard />}>
        <ResultListSection
          keyword={keyword}
          scope={scope}
          active={active}
          page={page}
          onPageChange={setPage}
        />
      </ResultPageBody>
    </div>
  );
}
