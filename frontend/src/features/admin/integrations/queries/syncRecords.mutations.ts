import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import { parseApiError } from '@/shared/api/errors';

import type { SyncRecordRetryRequest, SyncRecordRetryResponse } from '../types/syncModel';
import { summarizeRetryOutcome } from '../utils/retryOutcome';

export const useSyncRecordRetry = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (request: SyncRecordRetryRequest): Promise<SyncRecordRetryResponse> => {
      const res = await api.post<SyncRecordRetryResponse>(API.sync.retryRecords, request);
      return res.data;
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['sync', 'records', 'gaps', variables.event_id],
      });
      queryClient.invalidateQueries({
        queryKey: ['admin', 'connector', 'targetStatus'],
      });

      // HTTP 200이어도 응답 본문이 부분/전면 실패를 담을 수 있다 — 본문 기준으로 알린다.
      const outcome = summarizeRetryOutcome(data);
      if (outcome.kind === 'success') {
        toast('재시도가 완료되었습니다.', {
          description: `${outcome.succeededCount.toLocaleString('ko-KR')}건이 다시 임베딩되었습니다.`,
        });
      } else if (outcome.kind === 'partial') {
        toast.warning('일부만 재시도에 성공했습니다.', {
          description: `${outcome.succeededCount.toLocaleString('ko-KR')}건 성공, ${outcome.failedCount.toLocaleString('ko-KR')}건은 여전히 실패 상태입니다.`,
        });
      } else {
        toast.error('재시도에 실패했습니다.', {
          description: `${outcome.failedCount.toLocaleString('ko-KR')}건이 다시 실패했습니다. 잠시 후 다시 시도해주세요.`,
        });
      }
    },
    onError: (error) => {
      // 이 라우트의 에러 바디는 3형태(HTTPException detail / 루트 code+message / 422 배열) —
      // parseApiError가 전부 처리한다
      toast.error('재시도에 실패했습니다.', { description: parseApiError(error).message });
    },
  });
};
