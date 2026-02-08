'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { chatQueries } from '@/shared/queries/chatroom.queries';
import { integrationQueries } from '@/shared/queries/integration.queries';
import type { SearchQuery } from '@/shared/types/query/search';
import { formatShortDate } from '@/shared/utils/formatDate';

import { JiraTicketList } from './JiraTicketList';
import { RecentSearchList } from './RecentSearchList';

export const RecentActivityExplorer = () => {
  const queriesQuery = useQuery(chatQueries.recentQueries());
  const jiraQuery = useQuery(integrationQueries.jira.tickets());

  const recentQueries = useMemo<SearchQuery[]>(() => {
    if (!queriesQuery.data?.content) return [];
    return queriesQuery.data.content.map((item) => ({
      query: item.query,
      sessionId: item.sessionId,
      date: formatShortDate(item.createdAt),
    }));
  }, [queriesQuery.data]);

  const jiraTickets = useMemo(() => {
    if (!jiraQuery.data) return [];
    return jiraQuery.data.map((ticket) => ({
      id: ticket.issueKey,
      label: ticket.summary,
    }));
  }, [jiraQuery.data]);

  if (queriesQuery.isLoading || jiraQuery.isLoading) {
    return <div className="text-gray-40 p-5">데이터를 불러오는 중입니다...</div>;
  }

  return (
    <>
      <RecentSearchList title="최근 질문" querys={recentQueries} />
      <JiraTicketList tickets={jiraTickets} title="최근 확인한 지라 티켓" />
    </>
  );
};
