'use client';

// /hybrid-search 컨테이너.
// URL `tools`(scope, immutable) + `active`(drill-down) 분리.
// scope = tools 있으면 그것, 없으면 5종 전체 fallback.
// 검색바 submit은 draftKeyword + draftChips를 한 번에 적용 → keyword/tools 동시 갱신.

import { useState } from 'react';

import { type ActiveTab, useHybridSearchUrlState } from '../hooks/useHybridSearchUrlState';
import { TOOL_FILTERS_ARRAY, type ToolFilter } from '../types/hybridSearchApi';
import CatchupPromoCard from './CatchupPromoCard';
import ResultListSection from './ResultListSection';
import ResultPageBody from './ResultPageBody';
import ResultPageHeader from './ResultPageHeader';

export default function HybridSearchResultPage() {
  const { keyword, tools, active, page, setKeyword, setActive, setPage, setKeywordAndTools } = useHybridSearchUrlState();

  // URL keyword 변경 시 draftKeyword 동기 reset — render-phase prev-value 패턴.
  const [draftKeyword, setDraftKeyword] = useState(keyword);
  const [prevKeyword, setPrevKeyword] = useState(keyword);
  if (prevKeyword !== keyword) {
    setPrevKeyword(keyword);
    setDraftKeyword(keyword);
  }

  // URL tools 변경 시 draftChips 동기 reset — 같은 prev-value 패턴.
  // 배열 비교는 join(',')로 값 비교 (parseTools가 매 렌더 새 배열 반환하므로 reference 비교 불가).
  const [draftChips, setDraftChips] = useState<ToolFilter[]>(tools);
  const toolsKey = tools.join(',');
  const [prevToolsKey, setPrevToolsKey] = useState(toolsKey);
  if (prevToolsKey !== toolsKey) {
    setPrevToolsKey(toolsKey);
    setDraftChips(tools);
  }

  // scope: chips 선택 있으면 그것, 없으면 5종 전체.
  const scope: ToolFilter[] = tools.length > 0 ? tools : TOOL_FILTERS_ARRAY;

  const handleSubmit = () => {
    setKeywordAndTools(draftKeyword, draftChips);
  };

  // X 버튼: keyword만 제거, tools(scope)는 보존 — 다음 입력 시 동일 scope 재사용.
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
        draftChips={draftChips}
        onDraftChipsChange={setDraftChips}
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
