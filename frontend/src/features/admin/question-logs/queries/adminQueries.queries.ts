import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type {
  PaginatedResponse,
  QueryDetailResponse,
  RecentQueryWithSaveStatusResponse,
} from '@/shared/types/query/api';

import type { AdminQueryParams } from '../types/questionLog';

const PAGE_SIZE = 50;

export const adminQueriesQueries = {
  all: () => ['admin', 'queries'] as const,

  /** 무한 스크롤용 이용자 질문 기록 */
  list: (params: Omit<AdminQueryParams, 'page' | 'size'>) =>
    infiniteQueryOptions({
      queryKey: [...adminQueriesQueries.all(), params] as const,
      queryFn: async ({ pageParam }): Promise<PaginatedResponse<RecentQueryWithSaveStatusResponse>> => {
        const res = await api.get<PaginatedResponse<RecentQueryWithSaveStatusResponse>>(API.admin.queries, {
          params: { ...params, page: pageParam, size: PAGE_SIZE },
        });
        return res.data;
      },
      initialPageParam: 1,
      getNextPageParam: (lastPage, allPages) => {
        const totalPages = Math.ceil(lastPage.total / PAGE_SIZE);
        return allPages.length < totalPages ? allPages.length + 1 : undefined;
      },
      enabled: !!params.target_user_id,
    }),

  /** 질문-답변 상세 조회 (QA 1쌍) */
  detail: (messageId: number) =>
    queryOptions({
      queryKey: [...adminQueriesQueries.all(), 'detail', messageId] as const,
      queryFn: async (): Promise<QueryDetailResponse> => {
        const res = await api.get<QueryDetailResponse>(API.chatrooms.queryDetail(messageId));
        return res.data;
      },
      enabled: messageId > 0,
    }),
};
