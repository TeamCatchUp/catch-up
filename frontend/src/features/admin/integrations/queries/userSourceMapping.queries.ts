import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  MappingStatusResponse,
  UserSourceMappingResponse,
  UserSourceMappingStatus,
} from '../types/userSourceMappingApi';

export const userSourceMappingQueries = {
  all: () => ['integrations', 'user-source-mapping'] as const,
  lists: () => [...userSourceMappingQueries.all(), 'list'] as const,
  statuses: () => [...userSourceMappingQueries.all(), 'status'] as const,

  list: (params: { mapping_status: UserSourceMappingStatus; page: number; size: number }) =>
    queryOptions({
      queryKey: [...userSourceMappingQueries.lists(), params] as const,
      queryFn: async (): Promise<UserSourceMappingResponse> => {
        const res = await api.get<UserSourceMappingResponse>(API.integrations.userSourceMapping.list, {
          params: {
            mapping_status: params.mapping_status,
            page: params.page,
            size: params.size,
          },
        });
        return res.data;
      },
    }),

  status: () =>
    queryOptions({
      queryKey: [...userSourceMappingQueries.statuses()] as const,
      queryFn: async (): Promise<MappingStatusResponse> => {
        const res = await api.get<MappingStatusResponse>(API.integrations.userSourceMapping.status);
        return res.data;
      },
    }),
};
