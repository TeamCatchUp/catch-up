'use client';

import { Fragment } from 'react';

import ListItem from '@/features/mypage/history/components/ListItem';
import { usePageModel } from '@/features/mypage/history/hooks/pageModel';
import BookmarkIcon from '@/public/icons/icon/bookmark.svg';
import SearchIcon from '@/public/icons/icon/search.svg';
import FilterDropdown from '@/shared/components/ui/filter-dropdown';
import { Separator } from '@/shared/components/ui/separator';
import { cn } from '@/shared/utils/cn';
import { PERIOD_OPTIONS, SORT_OPTIONS } from '@/shared/utils/dateGrouping';

export default function HistoryPage() {
  const {
    sort,
    setSort,
    period,
    setPeriod,
    savedOnly,
    setSavedOnly,
    searchTerm,
    setSearchTerm,
    groupedSections,
    isLoading,
    isError,
  } = usePageModel();

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-[120px]">
      <h1 className="text-heading-xlarge text-gray-80">질문 히스토리</h1>

      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <FilterDropdown options={SORT_OPTIONS} value={sort} onChange={setSort} />
            <FilterDropdown options={PERIOD_OPTIONS} value={period} onChange={setPeriod} />
            <button
              type="button"
              onClick={() => setSavedOnly((prev) => !prev)}
              className={cn(
                'flex h-9 max-w-[145px] min-w-9 cursor-pointer items-center justify-center gap-1 rounded-lg border px-2 py-1.5',
                savedOnly
                  ? 'border-blue-30 bg-blue-1'
                  : 'border-neutral-3 hover:bg-neutral-2 active:bg-neutral-3 bg-white',
              )}
            >
              <BookmarkIcon className={cn('size-5 shrink-0', savedOnly ? 'text-blue-55' : 'text-gray-70')} />
              <span className={cn('text-body-small whitespace-nowrap', savedOnly ? 'text-blue-55' : 'text-gray-80')}>
                저장한 답변
              </span>
            </button>
          </div>

          <label className="border-neutral-2 bg-neutral-1 focus-within:border-neutral-3 flex h-10 w-[280px] items-center gap-1.5 rounded-lg border px-3 py-2">
            <SearchIcon className="text-gray-30 size-5 shrink-0" />
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="질문, 키워드로 검색하세요."
              className="text-body-small text-gray-70 placeholder:text-gray-30 w-full bg-transparent outline-none"
            />
          </label>
        </div>

        {isLoading && <div className="text-body-small text-gray-40 px-1 py-4">데이터를 불러오는 중입니다...</div>}

        {isError && (
          <div className="text-body-small px-1 py-4 text-red-50">
            질문 히스토리를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
          </div>
        )}

        {!isLoading && !isError && groupedSections.length === 0 && (
          <div className="text-body-small text-gray-40 px-1 py-4">조건에 맞는 질문 히스토리가 없습니다.</div>
        )}

        {!isLoading && !isError && groupedSections.length > 0 && (
          <div className="flex flex-col">
            {groupedSections.map((section, index) => (
              <Fragment key={section.key}>
                <section className="flex flex-col gap-3">
                  <div className="px-2">
                    <span className="text-body-xsmall text-gray-50">{section.title}</span>
                  </div>
                  <div className="flex flex-col gap-2">
                    {section.items.map((item) => (
                      <ListItem key={item.id} item={item} group={section.key} />
                    ))}
                  </div>
                </section>
                {index < groupedSections.length - 1 && <Separator className="my-6" />}
              </Fragment>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
