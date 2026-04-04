import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { AdminUserDetailResponse, AdminUserListResponse, EntryRequest } from '../types/adminMemberModel';

export const adminMembersQueries = {
  all: () => ['admin', 'members'] as const,

  list: () =>
    queryOptions({
      queryKey: [...adminMembersQueries.all(), 'list'] as const,
      queryFn: async (): Promise<AdminUserListResponse> => {
        const res = await api.get<AdminUserListResponse>(API.admin.users.list);
        return res.data;
      },
    }),

  detail: (userId: number) =>
    queryOptions({
      queryKey: [...adminMembersQueries.all(), 'detail', userId] as const,
      queryFn: async (): Promise<AdminUserDetailResponse> => {
        const res = await api.get<AdminUserDetailResponse>(API.admin.users.detail(userId));
        return res.data;
      },
      enabled: !!userId,
    }),

  requests: () =>
    queryOptions({
      queryKey: [...adminMembersQueries.all(), 'requests'] as const,
      queryFn: async (): Promise<EntryRequest[]> => {
        const res = await api.get<EntryRequest[]>(API.admin.members.requests);
        return res.data;
      },
    }),
};
