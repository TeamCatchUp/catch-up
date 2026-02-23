import { queryOptions } from '@tanstack/react-query';

import {
  MOCK_DAILY_USAGE,
  MOCK_QUESTION_COUNTS,
  MOCK_SUMMARY,
  MOCK_TOTAL_TREND,
} from '../mocks/tokenUsageMockData';

export const tokenUsageQueries = {
  all: () => ['admin', 'tokenUsage'] as const,

  summary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'summary'] as const,
      queryFn: async () => MOCK_SUMMARY,
    }),

  dailyUsage: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'dailyUsage'] as const,
      queryFn: async () => MOCK_DAILY_USAGE,
    }),

  totalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'totalTrend'] as const,
      queryFn: async () => MOCK_TOTAL_TREND,
    }),

  questionCounts: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'questionCounts'] as const,
      queryFn: async () => MOCK_QUESTION_COUNTS,
    }),
};
