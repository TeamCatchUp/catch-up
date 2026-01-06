import clsx from 'clsx';
import { useState } from 'react';
import Align from '/public/icons/icon/align.svg';
import Divider from '/public/icons/icon/divider.svg';
import SourceCardsComponent from '@/components/rag/rightComponent/sourceComponent/SourceCardsComponent';

interface Source {
  id: number;
  title: string;
  subtitle: string;
  content: string;
  date: string;
}

interface Props {
  sources: Source[];
}

const filterCategory = [
  { id: 1, category: '전체' },
  { id: 2, category: '첨부파일' },
  { id: 3, category: 'Wiki' },
  { id: 4, category: 'URL' },
  { id: 5, category: 'Github' },
  { id: 6, category: 'Slack' },
  { id: 7, category: '댓글' },
];

const SourceComponent = ({ sources }: Props) => {
  const [activeFilters, setActiveFilters] = useState<number[]>([]);

  const toggleFilter = (id: number) => {
    setActiveFilters((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
  };

  return (
    <div className="flex w-101.25 flex-col gap-3 px-4 py-3">
      {/* 필터링 */}
      <div className="-mb-4 flex w-full overflow-x-auto">
        <div className="flex h-9 min-w-max items-center gap-0.5">
          {/* Align */}
          <button className="outline-gray flex h-full w-9 shrink-0 cursor-pointer rounded-lg p-1.5">
            <Align className="block h-6 w-6 text-gray-50" />
          </button>

          {/* Divider */}
          <Divider className="text-neutral-4 block h-6 w-6 shrink-0" />

          {/* 필터 버튼 */}
          {filterCategory.map((category) => {
            const isActive = activeFilters.includes(category.id);

            return (
              <button
                key={category.id}
                onClick={() => toggleFilter(category.id)}
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
        {sources.map((source) => (
          <SourceCardsComponent key={source.id} source={source} />
        ))}
      </div>
    </div>
  );
};

export default SourceComponent;
