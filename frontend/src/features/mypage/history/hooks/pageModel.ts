'use client';

import { useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';

import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { RecentQueryWithSaveStatusResponse } from '@/shared/types/query/api';
import type { DatePeriod, GroupedSection, SortOrder } from '@/shared/utils/dateGrouping';
import { groupItemsByDate, isInPeriod as isInPeriodShared } from '@/shared/utils/dateGrouping';

import { useHistoryFilterStore } from '../store/historyFilterStore';
import type { HistoryItem } from '../types/historyModel';
import { toHistoryItem } from '../utils/mapHistory';

/** {@link usePageModel} 훅의 반환 타입 */
interface UsePageModelReturn {
  sort: SortOrder;
  setSort: (sort: SortOrder) => void;
  period: DatePeriod;
  setPeriod: (period: DatePeriod) => void;
  savedOnly: boolean;
  toggleSavedOnly: () => void;
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  groupedSections: GroupedSection<HistoryItem>[];
  isLoading: boolean;
  isError: boolean;
  /** 무한 스크롤: 다음 페이지 존재 여부 */
  hasNextPage: boolean;
  /** 무한 스크롤: 다음 페이지 로딩 중 여부 */
  isFetchingNextPage: boolean;
  /** 무한 스크롤: 다음 페이지 요청 */
  fetchNextPage: () => void;
}

/**
 * 질문 히스토리 페이지의 상태·데이터 로직을 관리하는 페이지 모델 훅.
 *
 * 무한 스크롤로 페이지를 누적 로드하고,
 * 정렬, 기간 필터, 저장 필터, 키워드 검색을 적용하여
 * 결과를 날짜 그룹(오늘 / 최근 7일 / 이전)별 섹션으로 반환한다.
 */
export const usePageModel = (): UsePageModelReturn => {
  const sort = useHistoryFilterStore((s) => s.sort);
  const setSort = useHistoryFilterStore((s) => s.setSort);
  const period = useHistoryFilterStore((s) => s.period);
  const setPeriod = useHistoryFilterStore((s) => s.setPeriod);
  const savedOnly = useHistoryFilterStore((s) => s.savedOnly);
  const toggleSavedOnly = useHistoryFilterStore((s) => s.toggleSavedOnly);
  const searchTerm = useHistoryFilterStore((s) => s.searchTerm);
  const setSearchTerm = useHistoryFilterStore((s) => s.setSearchTerm);

  const infiniteQuery = useInfiniteQuery(chatQueries.recentQueriesWithSaveStatusInfinite());

  const sourceItems = useMemo<RecentQueryWithSaveStatusResponse[]>(
    () => infiniteQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [infiniteQuery.data?.pages],
  );

  const historyItems = useMemo<HistoryItem[]>(() => sourceItems.map(toHistoryItem), [sourceItems]);

  const filteredItems = useMemo(() => {
    const normalizedKeyword = searchTerm.trim().toLowerCase();

    const next = historyItems
      .filter((item) => (savedOnly ? item.isSaved : true))
      .filter((item) => isInPeriodShared(item.rawDate, period))
      .filter((item) => {
        if (!normalizedKeyword) {
          return true;
        }
        return item.query.toLowerCase().includes(normalizedKeyword);
      });

    return next.sort((a, b) =>
      sort === 'latest' ? b.rawDate.getTime() - a.rawDate.getTime() : a.rawDate.getTime() - b.rawDate.getTime(),
    );
  }, [historyItems, period, savedOnly, searchTerm, sort]);

  const groupedSections = useMemo(() => groupItemsByDate(filteredItems, (item) => item.rawDate), [filteredItems]);

  return {
    sort,
    setSort,
    period,
    setPeriod,
    savedOnly,
    toggleSavedOnly,
    searchTerm,
    setSearchTerm,
    groupedSections,
    isLoading: infiniteQuery.isLoading,
    isError: infiniteQuery.isError,
    hasNextPage: infiniteQuery.hasNextPage,
    isFetchingNextPage: infiniteQuery.isFetchingNextPage,
    fetchNextPage: infiniteQuery.fetchNextPage,
  };
};
