import clsx from 'clsx';
import { useState } from 'react';
import Align from '/public/icons/icon/align.svg';
import Divider from '/public/icons/icon/divider.svg';
import SourceCardsComponent from '@/components/rag/rightComponent/sourceComponent/SourceCardsComponent';
import RagSourceSkeleton from '@/components/Skeleton/RagSourceSkeleton';

interface Props {
  sources: ChatSource[];
  isLoading?: boolean;
}

const filterCategory = [
  { id: 1, category: '전체', type: 'all' },
  { id: 2, category: '첨부파일', type: 'file' },
  { id: 3, category: 'Wiki', type: 'wiki' },
  { id: 4, category: 'URL', type: 'url' },
  { id: 5, category: 'Github', type: 'github' },
  { id: 6, category: 'Slack', type: 'slack' },
  { id: 7, category: '댓글', type: 'comment' },
] as const;

type FilterType = (typeof filterCategory)[number]['type'];

const SourceComponent = ({ sources, isLoading = false }: Props) => {
  const [activeFilters, setActiveFilters] = useState<FilterType[]>([]);

  const toggleFilter = (type: FilterType) => {
    if (type === 'all') {
      setActiveFilters([]);
      return;
    }

    setActiveFilters((prev) => (prev.includes(type) ? prev.filter((v) => v !== type) : [...prev, type]));
  };

  const filteredSources =
    activeFilters.length === 0 ? sources : sources.filter((source) => activeFilters.includes(source.sourceType));

  return (
    <div className="flex w-101.25 flex-col gap-3 px-4 py-3">
      {/* 필터링 */}
      <div className="-mb-4 flex w-full overflow-x-auto">
        <div className="flex h-9 min-w-max items-center gap-0.5">
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
                className={clsx(
                  'text-body-small flex h-full shrink-0 cursor-pointer items-center justify-center rounded-full px-3 leading-none whitespace-nowrap transition',
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

      <div className="flex flex-col gap-2">
        {/* 출처 카드 컴포넌트 */}
        {isLoading ? (
          <RagSourceSkeleton />
        ) : (
          filteredSources.map((source) => <SourceCardsComponent key={source.id} source={source} />)
        )}
      </div>
    </div>
  );
};

export default SourceComponent;
