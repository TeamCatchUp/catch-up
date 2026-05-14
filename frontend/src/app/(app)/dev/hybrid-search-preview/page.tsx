'use client';

// 하이브리드 검색 결과 페이지 컴포넌트들의 시각 카탈로그(임시).
// 본 라우트(/hybrid-search) 도입 시 처리 결정.

import { useState } from 'react';

import CatchupPromoCard from '@/features/hybrid-search/components/CatchupPromoCard';
import HybridSearchResultCard from '@/features/hybrid-search/components/HybridSearchResultCard';
import ResultEmptyState from '@/features/hybrid-search/components/ResultEmptyState';
import ResultErrorState from '@/features/hybrid-search/components/ResultErrorState';
import ResultLoadingState from '@/features/hybrid-search/components/ResultLoadingState';
import ResultSearchBar from '@/features/hybrid-search/components/ResultSearchBar';
import SearchHistoryList from '@/shared/components/SearchHistoryList';
import AccentTabs from '@/shared/components/ui/accent-tabs';
import type { DocsSource } from '@/shared/types/source';

type FilterTab = 'all' | DocsSource;

const FILTER_TABS = [
  { value: 'all' as const, label: '전체' },
  { value: 'confluence' as const, label: 'Confluence', count: 1 },
  { value: 'jira' as const, label: 'Jira', count: 1 },
  { value: 'slack' as const, label: 'Slack', count: 1 },
  { value: 'github' as const, label: 'Github', count: 1 },
  { value: 'channel_talk' as const, label: '채널톡', count: 1 },
];

import type { RagSourceUiModel } from '@/shared/types/ragSourceModel';

const MOCK_SOURCES: ReadonlyArray<RagSourceUiModel> = [
  {
    id: 'github:pr:1',
    source_type: 'github',
    entity_type: 'pr',
    is_cited: false,
    repo: 'catchup-team/catchup-frontend',
    title: 'feat(frontend): 하이브리드 검색 결과 페이지 컴포넌트 추가',
    content: '',
    date: '3일 전 변경',
    author: 'fkgrkyr',
    html_url: 'https://github.com/catchup-team/catchup-frontend/pull/1',
    source_index: 1,
    github_number: 1234,
  },
  {
    id: 'jira:issue:CATDEV-476',
    source_type: 'jira',
    entity_type: 'issue',
    is_cited: false,
    repo: 'CATDEV',
    title: '문서 탐색 결과 페이지 UI 구현',
    content: '',
    date: '1일 전 변경',
    author: '팀원D',
    html_url: '#',
    source_index: 2,
    issue_key: 'CATDEV-476',
  },
  {
    id: 'slack:message:1',
    source_type: 'slack',
    entity_type: 'message',
    is_cited: false,
    repo: '#frontend-team',
    title: '검색 결과 페이지 디자인 리뷰 요청드립니다',
    content: '',
    date: '5시간 전 변경',
    author: '디자이너',
    html_url: '#',
    source_index: 3,
  },
  {
    id: 'confluence:page:1',
    source_type: 'confluence',
    entity_type: 'page',
    is_cited: false,
    repo: 'CatchUp / 디자인 시스템',
    title: '하이브리드 검색 결과 페이지 사양 v0.3',
    content: '',
    date: '6일 전 변경',
    author: 'PM',
    html_url: '#',
    source_index: 4,
  },
  {
    id: 'channel_talk:user_chat:1',
    source_type: 'channel_talk',
    entity_type: 'user_chat',
    is_cited: false,
    repo: 'CS / 문의 응대',
    title: '검색 결과가 안 보여요',
    content: '',
    date: '방금 전 변경',
    author: '고객',
    html_url: '#',
    source_index: 5,
  },
];

export default function HybridSearchPreviewPage() {
  const [searchValue, setSearchValue] = useState('');
  const [searchValueFilled, setSearchValueFilled] = useState('지난주 결제 롤백');
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');

  return (
    <div className="bg-fill-strong flex min-h-full flex-col gap-10 px-8 py-10">
      <header className="flex flex-col gap-1">
        <h1 className="text-heading-xlarge text-content-normal">Hybrid Search — 컴포넌트 카탈로그</h1>
        <p className="text-body-small text-content-alternative">
          본 라우트가 아닌 dev 전용 프리뷰. 본 라우트(/hybrid-search) 도입 시 정리 예정.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">ResultSearchBar — collapsed (default)</h2>
        <p className="text-body-xsmall text-content-alternative">input을 클릭하면 expanded 시각으로 전환됨.</p>
        <div className="max-w-220">
          <ResultSearchBar
            value={searchValue}
            onValueChange={setSearchValue}
            chips={[]}
            onChipsChange={() => {}}
            onSubmit={() => {}}
            onHistorySubmit={() => {}}
            onClear={() => setSearchValue('')}
          />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">
          ResultSearchBar — expanded empty (Figma 13426:52872 입력 없을 때)
        </h2>
        <p className="text-body-xsmall text-content-alternative">SendButton 단독(inactive 회색).</p>
        <div className="max-w-220">
          <ResultSearchBar
            value={searchValue}
            onValueChange={setSearchValue}
            chips={[]}
            onChipsChange={() => {}}
            onSubmit={() => {}}
            onHistorySubmit={() => {}}
            onClear={() => setSearchValue('')}
            forceExpanded
          />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">
          ResultSearchBar — expanded has-text (Figma 13426:53946 입력 시)
        </h2>
        <p className="text-body-xsmall text-content-alternative">cancel + divider + SendButton(active 파랑).</p>
        <div className="max-w-220">
          <ResultSearchBar
            value={searchValueFilled}
            onValueChange={setSearchValueFilled}
            chips={[]}
            onChipsChange={() => {}}
            onSubmit={() => {}}
            onHistorySubmit={() => {}}
            onClear={() => setSearchValueFilled('')}
            forceExpanded
          />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">AccentTabs (필터 탭)</h2>
        <AccentTabs items={FILTER_TABS} value={activeFilter} onValueChange={setActiveFilter} ariaLabel="결과 필터 탭" />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">HybridSearchResultCard — 5개 소스 타입</h2>
        <div className="bg-fill-normal max-w-220 rounded-xl p-4">
          <ul className="flex flex-col gap-2">
            {MOCK_SOURCES.map((source) => (
              <li key={source.id}>
                <HybridSearchResultCard source={source} />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">CatchupPromoCard — 단독</h2>
        <CatchupPromoCard className="w-80" />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">SearchHistoryList — 빈 배열 (null 반환)</h2>
        <div className="bg-fill-normal flex max-w-180 items-center justify-center rounded-xl px-4 py-6">
          <SearchHistoryList entries={[]} />
          <span className="text-body-xsmall text-content-alternative">(빈 배열이면 DOM 미렌더)</span>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">ResultLoadingState</h2>
        <div className="bg-fill-normal max-w-180 rounded-xl">
          <ResultLoadingState />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">ResultEmptyState</h2>
        <div className="bg-fill-normal max-w-180 rounded-xl">
          <ResultEmptyState />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading-medium text-content-normal">ResultErrorState</h2>
        <div className="bg-fill-normal max-w-180 rounded-xl">
          <ResultErrorState onRetry={() => console.log('retry clicked')} />
        </div>
      </section>
    </div>
  );
}
