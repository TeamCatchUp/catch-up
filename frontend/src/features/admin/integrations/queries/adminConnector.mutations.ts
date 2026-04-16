import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { FullSyncRequest, SyncAcceptedResponse } from '../types/syncModel';

export const adminConnectorMutations = {
  syncFull: () =>
    ({
      mutationKey: ['admin', 'sync', 'full'] as const,
      mutationFn: (body: FullSyncRequest) => api.post<SyncAcceptedResponse>(API.sync.full, body),
    }) satisfies UseMutationOptions<AxiosResponse<SyncAcceptedResponse>, Error, FullSyncRequest>,

  syncOAuthUsers: () =>
    ({
      mutationKey: ['admin', 'oauth-users', 'sync'] as const,
      mutationFn: () => api.post<{ message: string }>(API.admin.users.syncOAuthUsers),
      meta: { invalidates: [['admin', 'users', 'syncStatus']] },
    }) satisfies UseMutationOptions<AxiosResponse<{ message: string }>, Error, void>,

  slackIncrementalRecovery: () =>
    ({
      mutationKey: ['admin', 'sync', 'slack-incremental-recovery'] as const,
      mutationFn: () => api.post(API.sync.slackIncrementalRecovery),
    }) satisfies UseMutationOptions<AxiosResponse, Error, void>,
};
