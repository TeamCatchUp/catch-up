'use client';

import { JiraTicketList } from './JiraTicketList';
import { RecentSearchList } from './RecentSearchList';
import { useEffect, useState } from 'react';
import { searchService } from '@/api/search';
import { formatShortDate } from '@/util/shared/formatDate';
import type { SearchQuery } from '@/types/search/search';

export const RecentActivityExplorer = () => {
  const [recentQueries, setRecentQueries] = useState<SearchQuery[]>([]);
  const [jiraTickets, setJiraTickets] = useState<{ id: string; label: string }[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchDefaultData = async () => {
      try {
        setIsLoading(true);

        const [queriesRes, jiraRes] = await Promise.all([
          searchService.getRecentQueries(),
          searchService.getRecentJiraTickets(),
        ]);

        if (queriesRes.content) {
          const mappedQueries: SearchQuery[] = queriesRes.content.map((item) => ({
            query: item.query,
            sessionId: item.sessionId,
            date: formatShortDate(item.createdAt),
          }));
          setRecentQueries(mappedQueries);
        }

        const mappedTickets = jiraRes.map((ticket) => ({
          id: ticket.issueKey,
          label: ticket.summary,
        }));
        setJiraTickets(mappedTickets);
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
    <>
      <RecentSearchList title="최근 질문" querys={recentQueries} />
      <JiraTicketList tickets={jiraTickets} title="최근 확인한 지라 티켓" />
    </>
  );
};
