import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { AuthUser } from './auth.types';

export const authQueries = {
  all: () => ['auth'] as const,

  me: () =>
    queryOptions({
      queryKey: [...authQueries.all(), 'me'] as const,
      queryFn: async (): Promise<AuthUser> => {
        const res = await api.get<AuthUser>(API.auth.me);
        return res.data;
      },
      retry: false,
    }),
};
