import { queryOptions } from '@tanstack/react-query';

// TODO: 백엔드 API 준비 시 실제 API 호출로 교체
// Mock 버전: src/shared/mocks/admin/token-usage/tokenUsage.queries.ts

export const tokenUsageQueries = {
  all: () => ['admin', 'tokenUsage'] as const,

  /* ── 나의 토큰 사용량 ── */

  summary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'summary'] as const,
      queryFn: async () => ({ total_cost: 0, status: 'normal' as const }),
    }),

  dailyUsage: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'dailyUsage'] as const,
      queryFn: async () => [],
    }),

  totalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'totalTrend'] as const,
      queryFn: async () => [],
    }),

  questionCounts: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'questionCounts'] as const,
      queryFn: async () => [],
    }),

  /* ── 조직 토큰 사용량 ── */

  orgMembers: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgMembers'] as const,
      queryFn: async () => [],
    }),

  orgSummary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgSummary'] as const,
      queryFn: async () => ({ total_cost: 0, status: 'normal' as const }),
    }),

  orgDailyUsage: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgDailyUsage'] as const,
      queryFn: async () => [],
    }),

  orgTotalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgTotalTrend'] as const,
      queryFn: async () => [],
    }),

  orgQuestionCounts: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgQuestionCounts'] as const,
      queryFn: async () => [],
    }),

  orgRanking: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgRanking'] as const,
      queryFn: async () => [],
    }),

  /* ── 이용자 관리 ── */

  userManagement: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'userManagement'] as const,
      queryFn: async () => [],
    }),

  /* ── 제한 해제 요청 ── */

  limitReleaseRequests: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'limitReleaseRequests'] as const,
      queryFn: async () => [],
    }),
};
