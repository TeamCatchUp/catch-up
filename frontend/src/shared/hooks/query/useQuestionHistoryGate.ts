'use client';

import { useQuery } from '@tanstack/react-query';

import { chatQueries } from '@/shared/queries/chatroom.queries';

interface UseQuestionHistoryGateReturn {
  shouldShowNoHistoryBox: boolean;
  isLoading: boolean;
}

export const useQuestionHistoryGate = (): UseQuestionHistoryGateReturn => {
  const recentQueriesQuery = useQuery(chatQueries.recentQueries());

  const items = recentQueriesQuery.data?.items;

  // 비어있지 않은/에러/비정상 응답은 모두 기존 UI 유지
  const shouldShowNoHistoryBox = !recentQueriesQuery.isError && Array.isArray(items) && items.length === 0;

  return {
    shouldShowNoHistoryBox,
    isLoading: recentQueriesQuery.isLoading,
  };
};

export default useQuestionHistoryGate;
