import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { FullSyncRequest, SyncAcceptedResponse } from '../types/sync';

export const adminConnectorMutations = {
  syncFull: () =>
    ({
      mutationKey: ['admin', 'sync', 'full'] as const,
      mutationFn: (body: FullSyncRequest) => api.post<SyncAcceptedResponse>(API.sync.full, body),
    }) satisfies UseMutationOptions<AxiosResponse<SyncAcceptedResponse>, Error, FullSyncRequest>,
};
