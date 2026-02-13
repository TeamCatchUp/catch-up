'use client';

import { useMemo, useState } from 'react';

import RagSourceSkeleton from '@/features/chat/components/skeleton/RagRightComponentSkeleton';
import { cn } from '@/shared/utils/cn';

import SourceCard from './SourceCard';
import SourceError from './SourceError';

import AddCircle from '/public/icons/icon/add_circle.svg';

interface Props {
  sources: ChatSource[];
  isLoading?: boolean;
  isError?: boolean;
}

const filterCategory = [
  { id: 1, category: '전체', type: 'all' },
  { id: 2, category: 'Github', type: 'github' },
  { id: 3, category: 'Jira', type: 'jira' },
  { id: 4, category: 'Slack', type: 'slack' },
] as const;

type FilterType = (typeof filterCategory)[number]['type'];

const SourceList = ({ sources, isLoading, isError }: Props) => {
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');

  const toggleFilter = (type: FilterType) => {
    setActiveFilter(type);
  };

  const getSourceCategory = (t: ChatSource['source_type']): Exclude<FilterType, 'all'> => {
    switch (t) {
      case 'jira':
        return 'jira';
      case 'slack':
        return 'slack';
      case 'code':
      case 'pr':
      case 'github_issue':
        return 'github';
    }
  };

  const filteredSources = useMemo(() => {
    if (activeFilter === 'all') {
      return sources;
    }

    if (activeFilter === 'slack') {
      return [];
    }

    return sources.filter((source) => getSourceCategory(source.source_type) === activeFilter);
  }, [activeFilter, sources]);

  const citedSources = filteredSources
    .filter((source) => source.is_cited)
    .sort((a, b) => a.source_index - b.source_index);
  const recommendedSources = filteredSources.filter((source) => !source.is_cited);

  return (
    <div className="flex min-h-full w-full flex-col gap-2 pt-3">
      <div className="no-scrollbar flex w-full items-center gap-2 overflow-x-auto px-4">
        {filterCategory.map((category) => {
          const isActive = activeFilter === category.type;

          return (
            <button
              key={category.id}
              type="button"
              onClick={() => toggleFilter(category.type)}
              className={cn(
                'text-body-small flex h-9 shrink-0 cursor-pointer items-center justify-center rounded-full border px-3 py-1.5 leading-none whitespace-nowrap transition',
                isActive
                  ? 'border-neutral-80 bg-neutral-80 text-white'
                  : 'border-neutral-3 bg-white text-gray-70 hover:bg-neutral-2',
              )}
            >
              {category.category}
            </button>
          );
        })}
      </div>

      <div className="flex flex-1 flex-col gap-3">
        {isError ? (
          <div className="px-4">
            <SourceError />
          </div>
        ) : isLoading ? (
          <div className="px-4">
            <RagSourceSkeleton message={'출처를 분석하는 중입니다.'} />
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-3 px-4">
              {citedSources.map((source) => (
                <SourceCard
                  key={source.id}
                  source={source}
                  showCount
                  count={source.source_index}
                />
              ))}
            </div>
            {recommendedSources.length > 0 && (
              <>
                <div className="bg-neutral-3 mt-1 h-px w-full" />
                <div className="flex flex-col gap-2.5 px-4 pb-6">
                  <div className="flex items-center gap-1.5 px-1.5">
                    <AddCircle className="text-gray-70 h-5 w-5" />
                    <span className="text-body-small text-gray-70">참고하면 좋은 문서들</span>
                  </div>
                  <div className="flex flex-col gap-2.5">
                    {recommendedSources.map((source) => (
                      <SourceCard
                        key={source.id}
                        source={source}
                        showCount={false}
                      />
                    ))}
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default SourceList;
