'use client';

import { Fragment, useMemo, useState } from 'react';

import BookmarkIcon from '@/public/icons/icon/bookmark.svg';
import SearchIcon from '@/public/icons/icon/search.svg';
import FilterDropdown from '@/shared/components/ui/filter-dropdown';
import { Separator } from '@/shared/components/ui/separator';
import { cn } from '@/shared/utils/cn';
import {
  type DatePeriod,
  groupItemsByDate,
  isInPeriod,
  PERIOD_OPTIONS,
  SORT_OPTIONS,
  type SortOrder,
} from '@/shared/utils/dateGrouping';

import type { QuestionLogItem } from '../../types/questionLog';
import QuestionLogListItem from '../QuestionLogListItem';

interface QuestionLogListSectionProps {
  items: QuestionLogItem[];
  userId: string;
}

/** 이용자 질문 기록 — 필터 + 날짜별 그룹 리스트 섹션 */
const QuestionLogListSection = ({ items, userId }: QuestionLogListSectionProps) => {
  const [sort, setSort] = useState<SortOrder>('latest');
  const [period, setPeriod] = useState<DatePeriod>('all');
  const [savedOnly, setSavedOnly] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const filteredItems = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase();

    const filtered = items
      .filter((item) => (savedOnly ? item.isSaved : true))
      .filter((item) => isInPeriod(item.rawDate, period))
      .filter((item) => !keyword || item.query.toLowerCase().includes(keyword));

    return filtered.sort((a, b) =>
      sort === 'latest' ? b.rawDate.getTime() - a.rawDate.getTime() : a.rawDate.getTime() - b.rawDate.getTime(),
    );
  }, [items, sort, period, savedOnly, searchTerm]);

  const groupedSections = useMemo(
    () => groupItemsByDate(filteredItems, (item) => item.rawDate),
    [filteredItems],
  );

  return (
    <div className="flex flex-col gap-4">
      {/* 필터 툴바 */}
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
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="질문, 키워드로 검색하세요."
            className="text-body-small text-gray-70 placeholder:text-gray-30 w-full bg-transparent outline-none"
          />
        </label>
      </div>

      {/* 그룹별 리스트 */}
      {groupedSections.length === 0 && (
        <div className="text-body-small text-gray-40 px-1 py-4">조건에 맞는 질문 기록이 없습니다.</div>
      )}

      {groupedSections.length > 0 && (
        <div className="flex flex-col">
          {groupedSections.map((section, index) => (
            <Fragment key={section.key}>
              <section className="flex flex-col gap-3">
                <div className="px-2">
                  <span className="text-body-xsmall text-gray-50">{section.title}</span>
                </div>
                <div className="flex flex-col gap-2">
                  {section.items.map((item) => (
                    <QuestionLogListItem key={item.id} item={item} group={section.key} userId={userId} />
                  ))}
                </div>
              </section>
              {index < groupedSections.length - 1 && <Separator className="my-6" />}
            </Fragment>
          ))}
        </div>
      )}
    </div>
  );
};

export default QuestionLogListSection;
