'use client';

import { useEffect, useMemo, useState } from 'react';

import { getCitationDisplayOrderMap } from '@/features/chat/components/answer/markdown/RenderWithBadges';
import RagSourceSkeleton from '@/features/chat/components/skeleton/RagRightComponentSkeleton';
import type { ChatSource } from '@/features/chat/types';
import AddCircle from '@/public/icons/icon/add_circle_filled.svg';
import { cn } from '@/shared/utils/cn';

import SourceCard from './SourceCard';
import SourceError from './SourceError';

interface Props {
  sources: ChatSource[];
  answerContent?: string;
  isLoading?: boolean;
  isError?: boolean;
  transitionKey?: string;
  prefersReducedMotion?: boolean;
}

const filterCategory = [
  { id: 1, category: '전체', type: 'all' },
  { id: 2, category: 'Github', type: 'github' },
  { id: 3, category: 'Jira', type: 'jira' },
  { id: 4, category: 'Confluence', type: 'confluence' },
  { id: 5, category: 'Slack', type: 'slack' },
] as const;

type FilterType = (typeof filterCategory)[number]['type'];

const STAGGER_STEP_MS = 24;
const STAGGER_MAX_DELAY_MS = 120;

const SourceList = ({
  sources,
  answerContent,
  isLoading,
  isError,
  transitionKey = 'default',
  prefersReducedMotion = false,
}: Props) => {
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const [listEntered, setListEntered] = useState(prefersReducedMotion);

  useEffect(() => {
    if (prefersReducedMotion) return;

    let enterRafId = 0;
    const resetRafId = requestAnimationFrame(() => {
      setListEntered(false);
      enterRafId = requestAnimationFrame(() => {
        setListEntered(true);
      });
    });

    return () => {
      cancelAnimationFrame(resetRafId);
      if (enterRafId) cancelAnimationFrame(enterRafId);
    };
  }, [prefersReducedMotion, transitionKey]);

  const validIndices = useMemo(() => new Set(sources.map((s) => s.source_index)), [sources]);
  const citationOrderMap = useMemo(
    () => getCitationDisplayOrderMap(answerContent ?? '', validIndices),
    [answerContent, validIndices],
  );

  /** 칩별 카운트: 전체 = unknown 포함 총량, 플랫폼별 = 해당 source_type만 */
  const sourceCounts = useMemo<Record<FilterType, number>>(() => {
    const counts = { all: sources.length, github: 0, jira: 0, slack: 0, confluence: 0 };
    for (const s of sources) {
      if (
        s.source_type === 'github' ||
        s.source_type === 'jira' ||
        s.source_type === 'slack' ||
        s.source_type === 'confluence'
      ) {
        counts[s.source_type] += 1;
      }
    }
    return counts;
  }, [sources]);

  const filteredSources = useMemo(() => {
    if (activeFilter === 'all') return sources;
    return sources.filter((source) => source.source_type === activeFilter);
  }, [activeFilter, sources]);

  const citedSources = filteredSources
    .filter((source) => source.is_cited)
    .sort((a, b) => {
      const orderA = citationOrderMap.get(a.source_index);
      const orderB = citationOrderMap.get(b.source_index);

      if (orderA !== undefined && orderB !== undefined) return orderA - orderB;
      if (orderA !== undefined) return -1;
      if (orderB !== undefined) return 1;
      return a.source_index - b.source_index;
    });

  const recommendedSources = filteredSources.filter((source) => !source.is_cited);

  const buildStaggerStyle = (index: number) => {
    if (prefersReducedMotion) return undefined;
    const delay = Math.min(index * STAGGER_STEP_MS, STAGGER_MAX_DELAY_MS);
    return { transitionDelay: `${delay}ms` };
  };

  const itemTransitionClass = prefersReducedMotion
    ? ''
    : cn(
        'transition-[opacity,transform] duration-160 ease-out',
        listEntered ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0',
      );

  return (
    <div className="flex min-h-full w-full flex-col gap-2 pt-3">
      {/* 상단 필터 탭 */}
      <div
        className={cn(
          'no-scrollbar flex w-full items-center gap-2 overflow-x-auto px-4',
          !prefersReducedMotion && 'transition-opacity duration-160 ease-out',
          !prefersReducedMotion && (listEntered ? 'opacity-100' : 'opacity-0'),
        )}
      >
        {filterCategory.map((category) => {
          const isActive = activeFilter === category.type;
          const count = sourceCounts[category.type];

          return (
            <button
              key={category.id}
              type="button"
              onClick={() => setActiveFilter(category.type)}
              className={cn(
                'text-body-small flex h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 whitespace-nowrap transition',
                isActive
                  ? 'border-accent-black-lighten bg-accent-black-lighten text-content-inverse'
                  : 'border-edge-neutral text-content-neutral hover:bg-fill-interaction-hover bg-fill-normal',
              )}
            >
              <span>{category.category}</span>
              <span
                className={cn(
                  'text-body-xsmall flex min-w-5 items-center justify-center rounded-full px-1',
                  isActive ? 'bg-dim-white-10' : 'bg-dim-black-10',
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>
      {/* 내부 SourceCard (Error + Loading) */}
      <div className="flex flex-1 flex-col gap-3">
        {isError ? (
          <div className="px-6">
            <SourceError />
          </div>
        ) : isLoading ? (
          <div className="px-6">
            <RagSourceSkeleton message="출처를 분석하는 중입니다." />
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-9 px-6">
              {citedSources.map((source, index) => (
                <div key={source.id} className={itemTransitionClass} style={buildStaggerStyle(index)}>
                  <SourceCard
                    source={source}
                    showCount
                    count={citationOrderMap.get(source.source_index) ?? source.source_index}
                  />
                </div>
              ))}
            </div>
            {/* 참고하면 좋은 문서 영역 */}
            {recommendedSources.length > 0 && (
              <>
                <div className="bg-edge-neutral mt-1 h-px w-full" />
                <div className="flex flex-col gap-2.5 px-6 pb-6">
                  <div className="flex items-center gap-1.5 px-1.5">
                    <AddCircle className="text-icon-primary-assistive h-5 w-5" />
                    <span className="text-body-small text-content-neutral">참고하면 좋은 문서</span>
                  </div>
                  <div className="flex flex-col gap-9">
                    {recommendedSources.map((source, index) => (
                      <div
                        key={source.id}
                        className={itemTransitionClass}
                        style={buildStaggerStyle(index + citedSources.length)}
                      >
                        <SourceCard source={source} showCount={false} />
                      </div>
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
