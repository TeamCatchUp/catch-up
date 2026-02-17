'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { USE_MOCK } from '@/shared/mocks/config';
import { MOCK_RECENT_QUERIES } from '@/shared/mocks/search/data';
import { chatQueries } from '@/shared/queries/chatroom.queries';

import { HISTORY_GROUP_ORDER, HISTORY_SECTION_LABELS } from '../constants/filterConfig';
import type { HistoryGroup, HistoryItem, HistoryPeriod, HistorySort } from '../types/models';
import { getHistoryGroup, isInPeriod, toHistoryItem } from '../utils/transformers';

/** 날짜 그룹별로 묶인 히스토리 섹션 */
interface GroupedSection {
  /** 섹션 식별 그룹 키 */
  key: HistoryGroup;
  /** 섹션 헤더에 표시할 제목 */
  title: string;
  /** 해당 그룹에 속하는 히스토리 아이템 목록 */
  items: HistoryItem[];
}

/** {@link usePageModel} 훅의 반환 타입 */
interface UsePageModelReturn {
  sort: HistorySort;
  setSort: React.Dispatch<React.SetStateAction<HistorySort>>;
  period: HistoryPeriod;
  setPeriod: React.Dispatch<React.SetStateAction<HistoryPeriod>>;
  savedOnly: boolean;
  setSavedOnly: React.Dispatch<React.SetStateAction<boolean>>;
  searchTerm: string;
  setSearchTerm: React.Dispatch<React.SetStateAction<string>>;
  groupedSections: GroupedSection[];
  isLoading: boolean;
  isError: boolean;
}

/**
 * 질문 히스토리 페이지의 상태·데이터 로직을 관리하는 페이지 모델 훅.
 *
 * 정렬, 기간 필터, 저장 필터, 키워드 검색을 적용하고
 * 결과를 날짜 그룹(오늘 / 최근 7일 / 이전)별 섹션으로 반환한다.
 */
export const usePageModel = (): UsePageModelReturn => {
  const [sort, setSort] = useState<HistorySort>('latest');
  const [period, setPeriod] = useState<HistoryPeriod>('all');
  const [savedOnly, setSavedOnly] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const recentQueriesQuery = useQuery(chatQueries.recentQueries());

  const sourceItems = useMemo(() => {
    if (USE_MOCK) {
      return MOCK_RECENT_QUERIES.items;
    }
    return recentQueriesQuery.data?.items ?? [];
  }, [recentQueriesQuery.data?.items]);

  const historyItems = useMemo<HistoryItem[]>(() => sourceItems.map(toHistoryItem), [sourceItems]);

  const filteredItems = useMemo(() => {
    const normalizedKeyword = searchTerm.trim().toLowerCase();

    const next = historyItems
      .filter((item) => (savedOnly ? item.isSaved : true))
      .filter((item) => isInPeriod(item, period))
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

  const groupedSections = useMemo<GroupedSection[]>(() => {
    const grouped: Record<HistoryGroup, HistoryItem[]> = {
      today: [],
      sevenDays: [],
      older: [],
    };

    for (const item of filteredItems) {
      const group = getHistoryGroup(item.rawDate);
      grouped[group].push(item);
    }

    return HISTORY_GROUP_ORDER.filter((group) => grouped[group].length > 0).map((group) => ({
      key: group,
      title: HISTORY_SECTION_LABELS[group],
      items: grouped[group],
    }));
  }, [filteredItems]);

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
    isLoading: !USE_MOCK && recentQueriesQuery.isLoading,
    isError: !USE_MOCK && recentQueriesQuery.isError,
  };
};
