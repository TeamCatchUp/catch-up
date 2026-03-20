import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

export const versionQueries = {
  all: () => ['version'] as const,

  current: () =>
    queryOptions({
      queryKey: [...versionQueries.all(), 'current'] as const,
      queryFn: async (): Promise<string> => {
        const res = await api.get<string>(API.version);
        return res.data;
      },
      staleTime: Infinity,
    }),
};
