import { queryOptions } from '@tanstack/react-query';
import { endOfDay, format } from 'date-fns';

import type { AdminUserListResponse } from '@/features/admin/members/types/adminMemberModel';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ChatTokenUsageParams,
  ChatTokenUsageResponse,
  QuestionCountResponse,
  UserTokenCostRankingResponse,
} from '../types/tokenUsageApi';
import type {
  DailyTokenUsage,
  LimitReleaseRequest,
  OrgMember,
  TokenUsageRankingEntry,
  TokenUsageSummary,
  TotalQuestionCount,
  TotalTokenUsageTrend,
} from '../types/tokenUsageModel';

// ── 헬퍼: DateRange → API params ──

function toApiParams(startDate?: Date, endDate?: Date): ChatTokenUsageParams | undefined {
  if (!startDate) return undefined;
  return {
    start_date: startDate.toISOString(),
    end_date: endDate ? endOfDay(endDate).toISOString() : undefined,
  };
}

// ── 헬퍼: API 응답 → 프론트 모델 변환 ──

function toDailyUsage(res: ChatTokenUsageResponse): DailyTokenUsage[] {
  return res.by_date.map((entry) => ({
    date: format(new Date(entry.from_date), 'yyyy-MM-dd'),
    cost: entry.usd,
  }));
}

function toQuestionCounts(res: QuestionCountResponse): TotalQuestionCount[] {
  return res.by_date.map((entry) => ({
    date: format(new Date(entry.from_date), 'yyyy-MM-dd'),
    count: entry.question_count,
  }));
}

function toRanking(res: UserTokenCostRankingResponse): TokenUsageRankingEntry[] {
  return res.ranking.map((item, index) => ({
    rank: index + 1,
    user_id: item.user_id,
    user_name: item.user_name,
    department: item.department,
    total_usd: item.total_usd,
  }));
}

// ── 쿼리 팩토리 ──

export const tokenUsageQueries = {
  all: () => ['admin', 'tokenUsage'] as const,

  /* ── 나의 토큰 사용량 ── */

  summary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'summary'] as const,
      queryFn: async (): Promise<TokenUsageSummary> => {
        const params: ChatTokenUsageParams = { start_date: '2026-01-01T00:00:00Z' };
        const res = await api.get<ChatTokenUsageResponse>(API.stats.myTokenCost, { params });
        return { total_cost: res.data.total_usd, daily_avg_usd: res.data.daily_avg_usd };
      },
    }),

  periodCost: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'periodCost',
        startDate,
        endDate,
      ] as const,
      queryFn: async () => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<ChatTokenUsageResponse>(API.stats.myTokenCost, { params });
        return { total_usd: res.data.total_usd, daily_avg_usd: res.data.daily_avg_usd };
      },
    }),

  dailyUsage: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'dailyUsage', startDate, endDate] as const,
      queryFn: async (): Promise<DailyTokenUsage[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<ChatTokenUsageResponse>(API.stats.myTokenCost, { params });
        return toDailyUsage(res.data);
      },
    }),

  // TODO: 누적 토큰 사용량 API 구현 시 교체
  totalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'totalTrend'] as const,
      queryFn: async (): Promise<TotalTokenUsageTrend[]> => [],
    }),

  questionCounts: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'questionCounts',
        startDate,
        endDate,
      ] as const,
      queryFn: async (): Promise<TotalQuestionCount[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<QuestionCountResponse>(API.stats.myQueries, { params });
        return toQuestionCounts(res.data);
      },
    }),

  /* ── 조직 토큰 사용량 ── */

  orgSummary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgSummary'] as const,
      queryFn: async (): Promise<TokenUsageSummary> => {
        const params: ChatTokenUsageParams = { start_date: '2026-01-01T00:00:00Z' };
        const res = await api.get<ChatTokenUsageResponse>(API.stats.orgTokenCost, { params });
        return { total_cost: res.data.total_usd, daily_avg_usd: res.data.daily_avg_usd };
      },
    }),

  orgDailyUsage: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'orgDailyUsage',
        startDate,
        endDate,
      ] as const,
      queryFn: async (): Promise<DailyTokenUsage[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<ChatTokenUsageResponse>(API.stats.orgTokenCost, { params });
        return toDailyUsage(res.data);
      },
    }),

  // TODO: 누적 토큰 사용량 API 구현 시 교체
  orgTotalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgTotalTrend'] as const,
      queryFn: async (): Promise<TotalTokenUsageTrend[]> => [],
    }),

  orgQuestionCounts: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'orgQuestionCounts',
        startDate,
        endDate,
      ] as const,
      queryFn: async (): Promise<TotalQuestionCount[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<QuestionCountResponse>(API.stats.orgQueries, { params });
        return toQuestionCounts(res.data);
      },
    }),

  orgMembers: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgMembers'] as const,
      queryFn: async (): Promise<OrgMember[]> => {
        const res = await api.get<AdminUserListResponse>(API.admin.users.list);
        return res.data.users.map((user) => ({
          id: String(user.id),
          name: user.name,
          team: user.department,
          position: user.jobLevel,
          role: user.role,
        }));
      },
    }),

  orgRanking: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'orgRanking',
        startDate,
        endDate,
      ] as const,
      queryFn: async (): Promise<TokenUsageRankingEntry[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<UserTokenCostRankingResponse>(API.stats.tokenRanking, { params });
        return toRanking(res.data);
      },
    }),

  /* ── 특정 유저 ── */

  userDailyUsage: (userId: number, startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'userDailyUsage',
        userId,
        startDate,
        endDate,
      ] as const,
      queryFn: async (): Promise<DailyTokenUsage[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<ChatTokenUsageResponse>(API.stats.userTokenCost(userId), { params });
        return toDailyUsage(res.data);
      },
    }),

  // TODO: 누적 토큰 사용량 API 구현 시 교체
  userTotalTrend: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'userTotalTrend'] as const,
      queryFn: async (): Promise<TotalTokenUsageTrend[]> => [],
    }),

  userQuestionCounts: (userId: number, startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'userQuestionCounts',
        userId,
        startDate,
        endDate,
      ] as const,
      queryFn: async (): Promise<TotalQuestionCount[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<QuestionCountResponse>(API.stats.userQueries(userId), { params });
        return toQuestionCounts(res.data);
      },
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
