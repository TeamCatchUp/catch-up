import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type { PaginatedResponse, RecentQueryWithSaveStatusResponse } from '@/shared/types/query/api';

import type { AdminQueryParams } from '../types/questionLog';

export const adminQueriesQueries = {
  all: () => ['admin', 'queries'] as const,

  list: (params: AdminQueryParams) =>
    queryOptions({
      queryKey: [...adminQueriesQueries.all(), params] as const,
      queryFn: async (): Promise<PaginatedResponse<RecentQueryWithSaveStatusResponse>> => {
        const res = await api.get<PaginatedResponse<RecentQueryWithSaveStatusResponse>>(API.admin.queries, {
          params,
        });
        return res.data;
      },
      enabled: !!params.target_user_id,
    }),
};
