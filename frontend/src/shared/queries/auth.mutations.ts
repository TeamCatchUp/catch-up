import type { UseMutationOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

export const authMutations = {
  logout: () =>
    ({
      mutationKey: ['auth', 'logout'] as const,
      mutationFn: () => api.post(API.auth.logout),
      meta: { invalidates: [] },
    }) satisfies UseMutationOptions,
};
