'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { SearchQuery } from '@/shared/types/query/search';
import { formatFullDate } from '@/shared/utils/formatDate';

import { RecentSearchList } from './RecentSearchList';

export const RecentActivityExplorer = () => {
  const queriesQuery = useQuery(chatQueries.recentQueries());

  const recentQueries = useMemo<SearchQuery[]>(() => {
    if (!queriesQuery.data?.items) return [];
    return queriesQuery.data.items.map((item) => ({
      query: item.content,
      session_id: item.session_id,
      date: formatFullDate(item.created_at),
      message_id: item.id > 0 ? item.id : undefined,
    }));
  }, [queriesQuery.data]);

  if (queriesQuery.isLoading) {
    return <div className="text-text-normal-alternative p-5">데이터를 불러오는 중입니다...</div>;
  }

  return <RecentSearchList title="최근 질문" querys={recentQueries} />;
};
