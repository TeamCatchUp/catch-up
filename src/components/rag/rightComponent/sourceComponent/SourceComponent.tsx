import clsx from 'clsx';
import { useState } from 'react';
import Align from '/public/icons/icon/align.svg';
import Divider from '/public/icons/icon/divider.svg';
import AddCircle from '/public/icons/icon/add_circle.svg';
import SourceCardsComponent from '@/components/rag/rightComponent/sourceComponent/SourceCardsComponent';
import RagSourceSkeleton from '@/components/Skeleton/RagSourceSkeleton';
import ErrorSourceComponent from './ErrorSourceComponent';

interface Props {
  sources: ChatSource[];
  isLoading?: boolean;
  isError?: boolean;
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

// 출처 자료 더미데이터
const MOCK_SOURCES: ChatSource[] = [
  {
    id: 1,
    sourceType: 'github',
    title: '잠재 파트너사 컨택 관련 (네이버)',
    subtitle: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본',
    content:
      '미리보기 text text text text text text text text text text text texttext text texttext text texttext text text text text texttext text text text text text text text text',
    date: '3일 전 변경',
    htmlUrl: 'https://www.naver.com',
    count: 1,
  },
  {
    id: 2,
    sourceType: 'wiki',
    title: '잠재 파트너사 컨택 관련 (구글)',
    subtitle: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본',
    content:
      '미리보기 text text text text text text text text text text text texttext text texttext text texttext text text text text texttext text text text text text text text text',
    date: '3일 전 변경',
    htmlUrl: 'https://www.google.com',
    count: 1,
  },
  {
    id: 3,
    sourceType: 'github',
    title: '잠재 파트너사 컨택 관련 (구글)',
    subtitle: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본',
    content:
      '미리보기 text text text text text text text text text text text texttext text texttext text texttext text text text text texttext text text text text text text text text',
    date: '3일 전 변경',
    htmlUrl: 'https://www.google.com',
    count: 0,
  },
];

const SourceComponent = ({ sources, isLoading, isError }: Props) => {
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

  // 출처 number 렌더링
  const sourcesWithNum = filteredSources.filter((source) => source.count && source.count > 0);
  const recommendedSources = filteredSources.filter((source) => !source.count || source.count === 0);

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

      <div className="mt-1 flex flex-col gap-2">
        {/* 출처 카드 컴포넌트 */}
        {isError ? (
          <ErrorSourceComponent />
        ) : isLoading ? (
          <RagSourceSkeleton />
        ) : (
          <div className="flex flex-col gap-2">
            {filteredSources.map((source) => (
              <SourceCardsComponent key={source.id} source={source} showCount count={source.count} />
            ))}

            {/* divider */}
            {recommendedSources.length > 0 && (
              <>
                <div className="bg-neutral-4 mt-1 mb-4 h-px w-93.25" />

                <div className="flex flex-col gap-2.5">
                  <div className="flex items-center gap-1.5 px-1.5">
                    <AddCircle className="text-gray-70 h-5 w-5" />
                    <span className="text-body-small text-gray-70 relative top-[1.5px]">참고하면 좋은 문서들</span>
                  </div>
                </div>
                {filteredSources.map((source) => (
                  <SourceCardsComponent key={source.id} source={source} showCount={false} />
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SourceComponent;
