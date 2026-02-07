'use client';

import { searchService } from '@/shared/api/search';
import { SearchHistory } from '@/shared/components/SearchHistory';
import { useEffect, useState } from 'react';
import { formatFullDate } from '@/shared/utils/formatDate';
import type { SearchQuery } from '@/types/search/search';

type SearchQueryWithRawDate = SearchQuery & { rawDate: Date };

export default function HistoryPage() {
  const [recentQueries, setRecentQueries] = useState<SearchQueryWithRawDate[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchDefaultData = async () => {
      try {
        setIsLoading(true);

        const [queriesRes] = await Promise.all([searchService.getRecentQueries()]);

        if (queriesRes.content) {
          const mappedQueries: SearchQueryWithRawDate[] = queriesRes.content.map((item) => ({
            query: item.query,
            sessionId: item.sessionId,
            date: formatFullDate(item.createdAt),
            rawDate: new Date(item.createdAt),
          }));
          setRecentQueries(mappedQueries);
        }
      } catch (err) {
        console.error('데이터 로드 실패:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDefaultData();
  }, []);

  if (isLoading) {
    return <div className="text-gray-40 p-5">데이터를 불러오는 중입니다...</div>;
  }

  return (
    <div className="mx-16 mt-6 mb-25">
      <SearchHistory querys={recentQueries} />
    </div>
  );
}
