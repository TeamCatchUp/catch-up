'use client';

import { useState } from 'react';

import RagSourceSkeleton from '@/features/chat/components/skeleton/RagRightComponentSkeleton';
import { cn } from '@/shared/utils/cn';

import SourceCard from './SourceCard';
import SourceError from './SourceError';

import AddCircle from '/public/icons/icon/add_circle.svg';
import Align from '/public/icons/icon/align.svg';
import Divider from '/public/icons/icon/divider.svg';

interface Props {
  sources: ChatSource[];
  isLoading?: boolean;
  isError?: boolean;
}

const filterCategory = [
  // { id: 1, category: '전체', type: 'all' },
  // { id: 2, category: '첨부파일', type: 'file' },
  // { id: 3, category: 'Wiki', type: 'wiki' },
  // { id: 4, category: 'URL', type: 'url' },
  // { id: 5, category: 'Github', type: 'github' },
  // { id: 6, category: 'Slack', type: 'slack' },
  // { id: 7, category: '댓글', type: 'comment' },
  { id: 1, category: '전체', type: 'all' },
  { id: 2, category: 'Jira', type: 'jira' },
  { id: 3, category: 'Github', type: 'github' },
] as const;

type FilterType = (typeof filterCategory)[number]['type'];

const SourceList = ({ sources, isLoading, isError }: Props) => {
  const [activeFilters, setActiveFilters] = useState<FilterType[]>([]);

  const toggleFilter = (type: FilterType) => {
    if (type === 'all') {
      setActiveFilters([]);
      return;
    }

    setActiveFilters((prev) => (prev.includes(type) ? prev.filter((v) => v !== type) : [...prev, type]));
  };

  const getSourceCategory = (t: ChatSource['sourceType']): Exclude<FilterType, 'all'> => {
    switch (t) {
      case 'jira':
        return 'jira';
      case 'code':
      case 'pr':
      case 'github_issue':
        return 'github';
    }
  };

  const filteredSources =
    activeFilters.length === 0
      ? sources
      : sources.filter((source) => activeFilters.includes(getSourceCategory(source.sourceType)));

  // 출처 number 렌더링
  const citedSources = filteredSources.filter((source) => source.isCited);
  const recommendedSources = filteredSources.filter((source) => !source.isCited);

  return (
    <div className="flex w-full flex-col gap-3 px-4 py-3">
      {/* 필터링 */}
      <div className="-mb-4 flex overflow-x-auto">
        <div className="flex h-9 items-center gap-0.5">
          {/* Align */}
          <button className="icon-button-only-gray flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg p-0.5">
            <Align className="block h-6 w-6 text-gray-50" />
          </button>

          {/* Divider */}
          <Divider className="text-neutral-4 block h-6 w-6 shrink-0" />

          {/* 필터 버튼 */}
          {filterCategory.map((category) => {
            const isActive =
              category.type === 'all' ? activeFilters.length === 0 : activeFilters.includes(category.type);

            return (
              <button
                key={category.id}
                onClick={() => toggleFilter(category.type)}
                className={cn(
                  'text-body-small mr-1.5 flex h-full shrink-0 cursor-pointer items-center justify-center rounded-full px-3 leading-none whitespace-nowrap transition',
                  isActive
                    ? 'border border-black bg-black text-white'
                    : 'border-neutral-3 text-gray-70 hover:bg-neutral-1 border bg-white',
                )}
              >
                {category.category}
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {/* 출처 카드 컴포넌트 */}
        {isError ? (
          <SourceError />
        ) : isLoading ? (
          <RagSourceSkeleton message={'출처를 분석하는 중입니다.'} />
        ) : (
          <div className="flex flex-col gap-2">
            {citedSources.map((source) => (
              <SourceCard key={source.id} source={source} showCount count={source.sourceIndex} />
            ))}

            {/* divider */}
            {recommendedSources.length > 0 && (
              <>
                <div className="bg-neutral-4 mt-1 mb-4 h-px w-107" />

                <div className="flex flex-col gap-2.5">
                  <div className="flex items-center gap-1.5 px-1.5">
                    <AddCircle className="text-gray-70 h-5 w-5" />
                    <span className="text-body-small text-gray-70 relative top-[1.5px]">참고하면 좋은 문서들</span>
                  </div>
                </div>
                {recommendedSources.map((source) => (
                  <SourceCard key={source.id} source={source} showCount={false} />
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SourceList;
