import { queryOptions } from '@tanstack/react-query';

import type {
  DailyTokenUsage,
  LimitReleaseRequest,
  OrgMember,
  TokenUsageRankingEntry,
  TokenUsageSummary,
  TotalQuestionCount,
  TotalTokenUsageTrend,
} from '../types/tokenUsage';

// TODO: 백엔드 API 준비 시 실제 API 호출로 교체
// Mock 버전: src/shared/mocks/admin/token-usage/tokenUsage.queries.ts

export const tokenUsageQueries = {
  all: () => ['admin', 'tokenUsage'] as const,

  /* ── 나의 토큰 사용량 ── */

  summary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'summary'] as const,
      queryFn: async (): Promise<TokenUsageSummary> => ({ total_cost: 0, status: 'normal' }),
    }),

  dailyUsage: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'dailyUsage'] as const,
      queryFn: async (): Promise<DailyTokenUsage[]> => [],
    }),

  totalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'totalTrend'] as const,
      queryFn: async (): Promise<TotalTokenUsageTrend[]> => [],
    }),

  questionCounts: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'questionCounts'] as const,
      queryFn: async (): Promise<TotalQuestionCount[]> => [],
    }),

  /* ── 조직 토큰 사용량 ── */

  orgMembers: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgMembers'] as const,
      queryFn: async (): Promise<OrgMember[]> => [],
    }),

  orgSummary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgSummary'] as const,
      queryFn: async (): Promise<TokenUsageSummary> => ({ total_cost: 0, status: 'normal' }),
    }),

  orgDailyUsage: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgDailyUsage'] as const,
      queryFn: async (): Promise<DailyTokenUsage[]> => [],
    }),

  orgTotalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgTotalTrend'] as const,
      queryFn: async (): Promise<TotalTokenUsageTrend[]> => [],
    }),

  orgQuestionCounts: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgQuestionCounts'] as const,
      queryFn: async (): Promise<TotalQuestionCount[]> => [],
    }),

  orgRanking: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgRanking'] as const,
      queryFn: async (): Promise<TokenUsageRankingEntry[]> => [],
    }),

  /* ── 이용자 관리 ── */

  userManagement: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'userManagement'] as const,
      queryFn: async (): Promise<OrgMember[]> => [],
    }),

  /* ── 제한 해제 요청 ── */

  limitReleaseRequests: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'limitReleaseRequests'] as const,
      queryFn: async (): Promise<LimitReleaseRequest[]> => [],
    }),
};
