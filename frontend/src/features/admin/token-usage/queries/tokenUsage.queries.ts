import { queryOptions } from '@tanstack/react-query';
import { endOfDay, format } from 'date-fns';

import type { AdminUserListResponse } from '@/features/admin/members/types/adminMemberModel';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { ChatTokenUsageParams, ChatTokenUsageResponse } from '../types/tokenUsageApi';
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
    model_name: 'total',
  }));
}

function toTotalTrend(res: ChatTokenUsageResponse): TotalTokenUsageTrend[] {
  let cumulative = 0;
  return res.by_date.map((entry) => {
    cumulative += entry.input_tokens + entry.output_tokens;
    return {
      date: format(new Date(entry.from_date), 'yyyy-MM-dd'),
      cumulative_tokens: cumulative,
    };
  });
}

// ── 쿼리 팩토리 ──

export const tokenUsageQueries = {
  all: () => ['admin', 'tokenUsage'] as const,

  /* ── 나의 토큰 사용량 ── */

  // TODO: summary API 별도 구현 시 교체
  summary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'summary'] as const,
      queryFn: async (): Promise<TokenUsageSummary> => ({ total_cost: 0, status: 'normal' }),
    }),

  dailyUsage: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'dailyUsage', startDate?.toISOString(), endDate?.toISOString()] as const,
      queryFn: async (): Promise<DailyTokenUsage[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<ChatTokenUsageResponse>(API.stats.myTokenCost, { params });
        return toDailyUsage(res.data);
      },
    }),

  totalTrend: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'totalTrend', startDate?.toISOString(), endDate?.toISOString()] as const,
      queryFn: async (): Promise<TotalTokenUsageTrend[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<ChatTokenUsageResponse>(API.stats.myTokenCost, { params });
        return toTotalTrend(res.data);
      },
    }),

  // TODO: 백엔드 미구현 — mock 유지
  questionCounts: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'questionCounts'] as const,
      queryFn: async (): Promise<TotalQuestionCount[]> => [],
    }),

  /* ── 조직 토큰 사용량 ── */

  // TODO: orgSummary API 별도 구현 시 교체
  orgSummary: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgSummary'] as const,
      queryFn: async (): Promise<TokenUsageSummary> => ({ total_cost: 0, status: 'normal' }),
    }),

  orgDailyUsage: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'orgDailyUsage',
        startDate?.toISOString(),
        endDate?.toISOString(),
      ] as const,
      queryFn: async (): Promise<DailyTokenUsage[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<ChatTokenUsageResponse>(API.stats.orgTokenCost, { params });
        return toDailyUsage(res.data);
      },
    }),

  orgTotalTrend: (startDate?: Date, endDate?: Date) =>
    queryOptions({
      queryKey: [
        ...tokenUsageQueries.all(),
        'orgTotalTrend',
        startDate?.toISOString(),
        endDate?.toISOString(),
      ] as const,
      queryFn: async (): Promise<TotalTokenUsageTrend[]> => {
        const params = toApiParams(startDate, endDate);
        const res = await api.get<ChatTokenUsageResponse>(API.stats.orgTokenCost, { params });
        return toTotalTrend(res.data);
      },
    }),

  // TODO: 백엔드 미구현 — mock 유지
  orgQuestionCounts: () =>
    queryOptions({
      queryKey: [...tokenUsageQueries.all(), 'orgQuestionCounts'] as const,
      queryFn: async (): Promise<TotalQuestionCount[]> => [],
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
          tokenEnabled: user.status === 'active',
          cost: 0,
        }));
      },
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
