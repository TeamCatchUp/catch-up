import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { PermissionMember, PermissionUserListResponse } from '../types/adminPermission';

export const adminPermissionsQueries = {
  all: () => ['admin', 'permissions'] as const,

  list: () =>
    queryOptions({
      queryKey: [...adminPermissionsQueries.all(), 'list'] as const,
      queryFn: async (): Promise<PermissionMember[]> => {
        const res = await api.get<PermissionUserListResponse>(API.admin.users.list);
        return res.data.users;
      },
    }),
};
