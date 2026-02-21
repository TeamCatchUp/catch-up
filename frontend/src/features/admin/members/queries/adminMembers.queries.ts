import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { AdminMember, EntryRequest } from '../types/adminMember';

export const adminMembersQueries = {
  all: () => ['admin', 'members'] as const,

  list: () =>
    queryOptions({
      queryKey: [...adminMembersQueries.all(), 'list'] as const,
      queryFn: async (): Promise<AdminMember[]> => {
        const res = await api.get<AdminMember[]>(API.admin.members.list);
        return res.data;
      },
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
