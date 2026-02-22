'use client';

import { useMemo, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';

import { USE_MOCK } from '@/shared/mocks/config';
import { MOCK_RECENT_QUERIES } from '@/shared/mocks/search/data';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { RecentQueryWithSaveStatusResponse } from '@/shared/types/query/api';
import type { DatePeriod, GroupedSection, SortOrder } from '@/shared/utils/dateGrouping';
import { groupItemsByDate, isInPeriod as isInPeriodShared } from '@/shared/utils/dateGrouping';

import type { HistoryItem } from '../types/models';
import { toHistoryItem } from '../utils/transformers';

/** {@link usePageModel} 훅의 반환 타입 */
interface UsePageModelReturn {
  sort: SortOrder;
  setSort: React.Dispatch<React.SetStateAction<SortOrder>>;
  period: DatePeriod;
  setPeriod: React.Dispatch<React.SetStateAction<DatePeriod>>;
  savedOnly: boolean;
  setSavedOnly: React.Dispatch<React.SetStateAction<boolean>>;
  searchTerm: string;
  setSearchTerm: React.Dispatch<React.SetStateAction<string>>;
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
  const [sort, setSort] = useState<SortOrder>('latest');
  const [period, setPeriod] = useState<DatePeriod>('all');
  const [savedOnly, setSavedOnly] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const infiniteQuery = useInfiniteQuery(chatQueries.recentQueriesWithSaveStatusInfinite());

  const sourceItems = useMemo<RecentQueryWithSaveStatusResponse[]>(() => {
    if (USE_MOCK) {
      return MOCK_RECENT_QUERIES.items.map((item) => ({
        ...item,
        is_answer_saved: false,
        answer_id: null,
      }));
    }
    return infiniteQuery.data?.pages.flatMap((page) => page.items) ?? [];
  }, [infiniteQuery.data?.pages]);

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
    setSavedOnly,
    searchTerm,
    setSearchTerm,
    groupedSections,
    isLoading: !USE_MOCK && infiniteQuery.isLoading,
    isError: !USE_MOCK && infiniteQuery.isError,
    hasNextPage: infiniteQuery.hasNextPage,
    isFetchingNextPage: infiniteQuery.isFetchingNextPage,
    fetchNextPage: infiniteQuery.fetchNextPage,
  };
};
