'use client';

// /hybrid-search 컨테이너. URL state + draftKeyword + activeTab 내부 state 보유.

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

  // URL keyword 변경 시 동기 reset — useEffect 대신 render-phase prev-value 패턴.
  // (React 공식 권장: https://react.dev/learn/you-might-not-need-an-effect)
  const [draftKeyword, setDraftKeyword] = useState(keyword);
  const [activeTab, setActiveTab] = useState<ActiveTab>('all');
  const [prevKeyword, setPrevKeyword] = useState(keyword);
  if (prevKeyword !== keyword) {
    setPrevKeyword(keyword);
    setDraftKeyword(keyword);
    setActiveTab('all');
  }

  const handleSubmit = () => {
    setKeyword(draftKeyword);
  };

  const handleClear = () => {
    setDraftKeyword('');
    setKeyword('');
  };

  const handleTabChange = (next: ActiveTab) => {
    setActiveTab(next);
    setTools(next === 'all' ? [] : [next]);
  };

  return (
    <div className="bg-fill-normal flex min-h-full flex-col">
      <ResultPageHeader
        keyword={keyword}
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
