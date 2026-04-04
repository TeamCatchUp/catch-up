'use client';

import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';

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

import { adminQueriesQueries } from '../../queries/adminQueries.queries';
import { useQuestionLogFilterStore } from '../../store/questionLogFilterStore';
import { toQuestionLogItem } from '../../utils/mapQuestionLog';
import QuestionLogListItem from '../QuestionLogListItem';

/** DatePeriod → API period 변환 (서버 사전 필터용) */
const toApiPeriod = (period: DatePeriod): 'today' | '7d' | '30d' | 'all' => {
  switch (period) {
    case 'today':
      return 'today';
    case 'sevenDays':
      return '7d';
    default:
      // 'older'와 'all'은 서버에서 전체 조회 후 클라이언트에서 후처리
      return 'all';
  }
};

interface QuestionLogListSectionProps {
  userId: number;
}

/** 이용자 질문 기록 — 서버사이드 필터 + 무한 스크롤 + 날짜별 그룹 리스트 섹션 */
export default function QuestionLogListSection({ userId }: QuestionLogListSectionProps) {
  const sort = useQuestionLogFilterStore((s) => s.sort);
  const setSort = useQuestionLogFilterStore((s) => s.setSort);
  const period = useQuestionLogFilterStore((s) => s.period);
  const setPeriod = useQuestionLogFilterStore((s) => s.setPeriod);
  const savedOnly = useQuestionLogFilterStore((s) => s.savedOnly);
  const toggleSavedOnly = useQuestionLogFilterStore((s) => s.toggleSavedOnly);
  const searchTerm = useQuestionLogFilterStore((s) => s.searchTerm);
  const setSearchTerm = useQuestionLogFilterStore((s) => s.setSearchTerm);

  const [debouncedSearch, setDebouncedSearch] = useState(searchTerm.trim());

  // 검색어 디바운스 (300ms) — timer 기반 외부 시스템 구독

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const handleSortChange = (value: SortOrder) => setSort(value);
  const handlePeriodChange = (value: DatePeriod) => setPeriod(value);
  const handleSavedOnlyToggle = () => toggleSavedOnly();

  const params = {
    target_user_id: userId,
    sort: sort === 'latest' ? ('desc' as const) : ('asc' as const),
    period: toApiPeriod(period),
    ...(savedOnly && { is_saved: true as const }),
    ...(debouncedSearch && { search: debouncedSearch }),
  };

  const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } = useInfiniteQuery(
    adminQueriesQueries.list(params),
  );

  const items = useMemo(() => {
    const all = (data?.pages.flatMap((page) => page.items) ?? []).map(toQuestionLogItem);
    // 서버 period는 시간 윈도우 기반이므로 클라이언트에서 날짜 그룹 기준 후처리
    if (period === 'all') return all;
    return all.filter((item) => isInPeriod(item.rawDate, period));
  }, [data?.pages, period]);

  const groupedSections = useMemo(() => groupItemsByDate(items, (item) => item.rawDate), [items]);

  /* 무한 스크롤 sentinel */
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  return (
    <div className="flex flex-col gap-4">
      {/* 필터 툴바 */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FilterDropdown options={SORT_OPTIONS} value={sort} onChange={handleSortChange} />
          <FilterDropdown options={PERIOD_OPTIONS} value={period} onChange={handlePeriodChange} />
          <button
            type="button"
            onClick={handleSavedOnlyToggle}
            className={cn(
              'flex h-9 max-w-[145px] min-w-9 cursor-pointer items-center justify-center gap-1 rounded-lg border px-2 py-1.5',
              savedOnly
                ? 'border-edge-primary bg-fill-primary-assistive'
                : 'border-edge-neutral hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed bg-fill-normal',
            )}
          >
            <BookmarkIcon className={cn('size-5 shrink-0', savedOnly ? 'text-icon-primary' : 'text-content-neutral')} />
            <span
              className={cn(
                'text-body-small whitespace-nowrap',
                savedOnly ? 'text-icon-primary' : 'text-content-normal',
              )}
            >
              저장한 답변
            </span>
          </button>
        </div>

        <label className="border-edge-assistive bg-fill-strong focus-within:border-edge-neutral flex h-10 w-[280px] items-center gap-1.5 rounded-lg border px-3 py-2">
          <SearchIcon className="text-content-assistive size-5 shrink-0" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="질문, 키워드로 검색하세요."
            className="text-body-small text-content-neutral placeholder:text-content-assistive w-full bg-transparent outline-none"
          />
        </label>
      </div>

      {/* 로딩 */}
      {isLoading && <div className="text-body-small text-content-assistive px-1 py-4">불러오는 중...</div>}

      {/* 빈 결과 */}
      {!isLoading && groupedSections.length === 0 && (
        <div className="text-body-small text-content-assistive px-1 py-4">조건에 맞는 질문 기록이 없습니다.</div>
      )}

      {/* 그룹별 리스트 */}
      {groupedSections.length > 0 && (
        <div className="flex flex-col">
          {groupedSections.map((section, index) => (
            <Fragment key={section.key}>
              <section className="flex flex-col gap-3">
                <div className="px-2">
                  <span className="text-body-xsmall text-content-alternative">{section.title}</span>
                </div>
                <div className="flex flex-col gap-2">
                  {section.items.map((item) => (
                    <QuestionLogListItem key={item.id} item={item} group={section.key} userId={String(userId)} />
                  ))}
                </div>
              </section>
              {index < groupedSections.length - 1 && <Separator className="my-6" />}
            </Fragment>
          ))}
        </div>
      )}

      {/* 무한 스크롤 sentinel + 로딩 표시 */}
      <div ref={sentinelRef} className="h-1" />
      {isFetchingNextPage && (
        <div className="text-body-small text-content-assistive py-2 text-center">불러오는 중...</div>
      )}
    </div>
  );
}
