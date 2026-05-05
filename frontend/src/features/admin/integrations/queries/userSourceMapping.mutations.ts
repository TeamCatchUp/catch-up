import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { UserSourceMappingRefreshResponse } from '../types/userSourceMappingApi';
import { userSourceMappingQueries } from './userSourceMapping.queries';

export const userSourceMappingMutations = {
  refresh: () =>
    ({
      mutationKey: ['integrations', 'user-source-mapping', 'refresh'] as const,
      mutationFn: () => api.post<UserSourceMappingRefreshResponse>(API.integrations.userSourceMapping.refresh),
      // QueryProvider는 meta.invalidates를 string[][]로 캐스팅하므로 readonly tuple을 spread로 mutable array로 확장.
      meta: { invalidates: [[...userSourceMappingQueries.all()]] },
    }) satisfies UseMutationOptions<AxiosResponse<UserSourceMappingRefreshResponse>, Error, void>,
};
