'use client';

import { searchService } from '@/api/search';
import { SearchHistory } from '@/components/shared/SearchHistory';
import { useEffect, useState } from 'react';

interface SearchQuery {
  query: string;
  sessionId: string;
  date: string;
  rawDate: Date;
}

export default function HistoryPage() {
  const [recentQueries, setRecentQueries] = useState<SearchQuery[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchDefaultData = async () => {
      try {
        setIsLoading(true);

        const [queriesRes] = await Promise.all([searchService.getRecentQueries()]);

        if (queriesRes.content) {
          const mappedQueries = queriesRes.content.map((item: any) => ({
            query: item.query,
            sessionId: item.sessionId,
            date: new Date(item.createdAt)
              .toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
              })
              .replace(/\s/g, '')
              .replace(/\.$/, ''),
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
