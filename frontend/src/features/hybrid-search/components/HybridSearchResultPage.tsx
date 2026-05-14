'use client';

// /hybrid-search 컨테이너. URL state + draftKeyword 보유.
// activeTab은 별도 state 없이 tools에서 derive — tools.length === 1이면 그 source, 아니면 'all'.

import { useState } from 'react';

import { useHybridSearchUrlState } from '../hooks/useHybridSearchUrlState';
import type { ToolFilter } from '../types/hybridSearchApi';
import CatchupPromoCard from './CatchupPromoCard';
import ResultListSection from './ResultListSection';
import ResultPageBody from './ResultPageBody';
import ResultPageHeader from './ResultPageHeader';

type ActiveTab = 'all' | ToolFilter;

export default function HybridSearchResultPage() {
  const { keyword, tools, page, setKeyword, setTools, setPage } = useHybridSearchUrlState();

  // URL keyword 변경 시 draftKeyword 동기 reset — render-phase prev-value 패턴.
  const [draftKeyword, setDraftKeyword] = useState(keyword);
  const [prevKeyword, setPrevKeyword] = useState(keyword);
  if (prevKeyword !== keyword) {
    setPrevKeyword(keyword);
    setDraftKeyword(keyword);
  }

  // activeTab derived from tools — 단일 tool이면 그 탭 활성, 아니면 '전체'.
  const activeTab: ActiveTab = tools.length === 1 ? tools[0] : 'all';

  const handleSubmit = () => {
    setKeyword(draftKeyword);
  };

  const handleClear = () => {
    setDraftKeyword('');
    setKeyword('');
  };

  // '전체' 클릭 → tools=[] (필터 해제, 모든 source 노출).
  // 특정 source 클릭 → tools=[그 source] (단일 source 좁히기).
  const handleTabChange = (next: ActiveTab) => {
    setTools(next === 'all' ? [] : [next]);
  };

  return (
    <div className="bg-fill-normal flex min-h-full flex-col">
      <ResultPageHeader
        keyword={keyword}
        tools={tools}
        draftKeyword={draftKeyword}
        onDraftKeywordChange={setDraftKeyword}
        onSubmit={handleSubmit}
        onClear={handleClear}
        activeTab={activeTab}
        onTabChange={handleTabChange}
      />
      <ResultPageBody side={<CatchupPromoCard />}>
        <ResultListSection keyword={keyword} tools={tools} page={page} onPageChange={setPage} />
      </ResultPageBody>
    </div>
  );
}
