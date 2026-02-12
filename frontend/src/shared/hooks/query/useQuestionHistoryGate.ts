'use client';

import { useQuery } from '@tanstack/react-query';

import { chatQueries } from '@/shared/queries/chatroom.queries';

interface UseQuestionHistoryGateReturn {
  shouldShowNoHistoryBox: boolean;
  isLoading: boolean;
}

export const useQuestionHistoryGate = (): UseQuestionHistoryGateReturn => {
  const recentQueriesQuery = useQuery(chatQueries.recentQueries());

  const content = recentQueriesQuery.data?.content;

  // Keep existing UI for all non-empty/error/invalid states.
  const shouldShowNoHistoryBox =
    !recentQueriesQuery.isError && Array.isArray(content) && content.length === 0;

  return {
    shouldShowNoHistoryBox,
    isLoading: recentQueriesQuery.isLoading,
  };
};

export default useQuestionHistoryGate;
