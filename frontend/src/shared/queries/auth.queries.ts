import { queryOptions } from '@tanstack/react-query';
import type { AxiosError } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { AuthUser, UserProfile } from './auth.types';

export const authQueries = {
  all: () => ['auth'] as const,

  me: () =>
    queryOptions({
      queryKey: [...authQueries.all(), 'me'] as const,
      queryFn: async (): Promise<AuthUser> => {
        const res = await api.get<AuthUser>(API.auth.me);
        return res.data;
      },
      retry: (failureCount, error) => {
        const status = (error as AxiosError)?.response?.status;
        if (status && status < 500) return false;
        return failureCount < 2;
      },
    }),

  profile: () =>
    queryOptions({
      queryKey: [...authQueries.all(), 'profile'] as const,
      queryFn: async (): Promise<UserProfile> => {
        const res = await api.get<UserProfile>(API.auth.profile);
        return res.data;
      },
    }),
};
