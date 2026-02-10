import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { ConnectorOptions } from './types/onboarding';

export const connectorQueries = {
  all: () => ['onboarding', 'connectors'] as const,
  list: () =>
    queryOptions({
      queryKey: connectorQueries.all(),
      queryFn: async (): Promise<ConnectorOptions> => {
        const res = await api.get<ConnectorOptions>(API.onboarding.connectors);
        return res.data;
      },
    }),
};
