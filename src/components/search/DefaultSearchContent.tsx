'use client';

import { JiraTicketList } from '@/components/UI/JiraTicketList';
import { ReacentlySearchList } from '@/components/UI/RecetlySearchList';
import { useEffect, useState } from 'react';
import { searchService } from '@/api/search';

interface SearchQuery {
  query: string;
  sessionId: string;
  date: string;
}

export const DefaultSearchContent = () => {
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
          const mappedQueries = queriesRes.content.map((item: any) => ({
            query: item.query,
            sessionId: item.sessionId,
            date: new Date(item.createdAt)
              .toLocaleDateString('ko-KR', {
                month: '2-digit',
                day: '2-digit',
              })
              .replace(/\. /g, '.')
              .slice(0, 5),
          }));
          setRecentQueries(mappedQueries);
        }

        const mappedTickets = jiraRes.map((ticket: any) => ({
          id: ticket.issueKey, // JIRA-101 형태
          label: ticket.summary, // 티켓 제목
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
      <ReacentlySearchList title="최근 질문" querys={recentQueries} />
      <JiraTicketList tickets={jiraTickets} title="최근 확인한 지라 티켓" />
    </>
  );
};
