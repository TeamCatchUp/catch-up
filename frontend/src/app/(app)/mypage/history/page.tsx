'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { SearchHistory } from '@/shared/components/SearchHistory';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { SearchQuery } from '@/shared/types/query/search';
import { formatFullDate } from '@/shared/utils/formatDate';

type SearchQueryWithRawDate = SearchQuery & { rawDate: Date };

export default function HistoryPage() {
  const { data, isLoading } = useQuery(chatQueries.recentQueries());

  const recentQueries = useMemo<SearchQueryWithRawDate[]>(() => {
    if (!data?.content) return [];
    return data.content.map((item) => ({
      query: item.query,
      sessionId: item.sessionId,
      date: formatFullDate(item.createdAt),
      rawDate: new Date(item.createdAt),
    }));
  }, [data]);

  if (isLoading) {
    return <div className="text-gray-40 p-5">데이터를 불러오는 중입니다...</div>;
  }

  return (
    <div className="mx-16 mt-6 mb-25">
      <SearchHistory querys={recentQueries} />
    </div>
  );
}
