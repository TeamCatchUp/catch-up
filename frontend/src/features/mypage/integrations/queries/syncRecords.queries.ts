import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { SyncRecordGapResponse } from '../types/sync';

/** event_id로 gap 데이터 조회 */
export const syncRecordGapsOptions = (eventId: string) =>
  queryOptions({
    queryKey: ['sync', 'records', 'gaps', eventId] as const,
    queryFn: async (): Promise<SyncRecordGapResponse> => {
      const res = await api.get<SyncRecordGapResponse>(API.sync.recordGaps, {
        params: { event_id: eventId },
      });
      return res.data;
    },
    enabled: !!eventId,
    staleTime: 30_000,
  });
