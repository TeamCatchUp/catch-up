import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { SyncRecordRetryRequest, SyncRecordRetryResponse } from '../types/syncModel';

export const useSyncRecordRetry = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (request: SyncRecordRetryRequest): Promise<SyncRecordRetryResponse> => {
      const res = await api.post<SyncRecordRetryResponse>(API.sync.retryRecords, request);
      return res.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['sync', 'records', 'gaps', variables.event_id],
      });
      queryClient.invalidateQueries({
        queryKey: ['admin', 'connector', 'targetStatus'],
      });
    },
    onError: (error) => {
      const message = (error as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(message ?? '재시도에 실패했습니다. 잠시 후 다시 시도해주세요.');
    },
  });
};
