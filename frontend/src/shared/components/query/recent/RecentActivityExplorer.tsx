'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { SearchQuery } from '@/shared/types/query/search';
import { formatShortDate } from '@/shared/utils/formatDate';

import { RecentSearchList } from './RecentSearchList';

export const RecentActivityExplorer = () => {
  const queriesQuery = useQuery(chatQueries.recentQueries());

  const recentQueries = useMemo<SearchQuery[]>(() => {
    if (!queriesQuery.data?.content) return [];
    return queriesQuery.data.content.map((item) => ({
      query: item.query,
      session_id: item.session_id,
      date: formatShortDate(item.created_at),
    }));
  }, [queriesQuery.data]);

  if (queriesQuery.isLoading) {
    return <div className="text-gray-40 p-5">데이터를 불러오는 중입니다...</div>;
  }

  return <RecentSearchList title="최근 질문" querys={recentQueries} />;
};
