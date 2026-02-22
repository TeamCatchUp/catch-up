import { infiniteQueryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type { PaginatedResponse, RecentQueryWithSaveStatusResponse } from '@/shared/types/query/api';

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
};
