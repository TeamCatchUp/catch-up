import { queryOptions } from '@tanstack/react-query';

import {
  MOCK_DAILY_USAGE,
  MOCK_ORG_DAILY_USAGE,
  MOCK_ORG_MEMBERS,
  MOCK_ORG_QUESTION_COUNTS,
  MOCK_ORG_RANKING,
  MOCK_ORG_SUMMARY,
  MOCK_ORG_TOTAL_TREND,
  MOCK_QUESTION_COUNTS,
  MOCK_SUMMARY,
  MOCK_TOTAL_TREND,
} from '../mocks/tokenUsageMockData';

export const tokenUsageQueries = {
  all: () => ['admin', 'tokenUsage'] as const,

  /* ── 나의 토큰 사용량 ── */

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

  /* ── 조직 토큰 사용량 ── */

  orgMembers: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgMembers'] as const,
      queryFn: async () => MOCK_ORG_MEMBERS,
    }),

  orgSummary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgSummary'] as const,
      queryFn: async () => MOCK_ORG_SUMMARY,
    }),

  orgDailyUsage: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgDailyUsage'] as const,
      queryFn: async () => MOCK_ORG_DAILY_USAGE,
    }),

  orgTotalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgTotalTrend'] as const,
      queryFn: async () => MOCK_ORG_TOTAL_TREND,
    }),

  orgQuestionCounts: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgQuestionCounts'] as const,
      queryFn: async () => MOCK_ORG_QUESTION_COUNTS,
    }),

  orgRanking: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgRanking'] as const,
      queryFn: async () => MOCK_ORG_RANKING,
    }),
};
