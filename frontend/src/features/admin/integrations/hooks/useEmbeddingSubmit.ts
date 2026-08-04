'use client';

import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { adminConnectorMutations } from '../queries/adminConnector.mutations';
import type { FullSyncTarget, SyncConnector } from '../types/syncModel';

interface UseEmbeddingSubmitOptions {
  /** accepted/conflict로 요청이 접수됐을 때 호출 — 모달 닫기 */
  onSettled: () => void;
  /** 임베딩 mutation 성공 시 useEmbeddingJobs로 job 추적 시작 콜백 */
  onJobStart?: (jobId: string, connector: SyncConnector) => void;
}

interface EmbeddingSubmitRequest {
  connector: SyncConnector;
  scopeId: string;
  targets: FullSyncTarget[];
  syncDays: number | null;
}

/**
 * 단일 scope 커넥터(임베딩 모달)의 임베딩 제출.
 * `EmbeddingModal`의 handleSubmit을 추출했다 — 응답 상태별 토스트와 job 추적 시작까지 담당한다.
 * 채널톡은 channel별 N회 호출·집계가 필요해 별도 훅(`useChannelTalkEmbeddingSubmit`)을 쓴다.
 */
export function useEmbeddingSubmit({ onSettled, onJobStart }: UseEmbeddingSubmitOptions) {
  const syncMutation = useMutation(adminConnectorMutations.syncFull());

  const submit = async ({ connector, scopeId, targets, syncDays }: EmbeddingSubmitRequest) => {
    try {
      const result = await syncMutation.mutateAsync({
        connector,
        scope_id: scopeId,
        targets,
        sync_days: syncDays,
      });

      const response = result.data;

      switch (response.status) {
        case 'accepted':
          toast('임베딩이 시작되었습니다.', { description: '준비가 끝나면 즉시 알려드릴게요.' });
          if (response.job_id) onJobStart?.(response.job_id, connector);
          onSettled();
          break;
        case 'conflict':
          toast.warning('이미 진행 중인 임베딩이 있습니다.');
          if (response.job_id) onJobStart?.(response.job_id, connector);
          onSettled();
          break;
        case 'no_events':
          toast.info('임베딩할 대상이 없습니다.');
          break;
        case 'failed':
          toast('임베딩 요청에 실패했습니다.', { description: response.message });
          break;
      }
    } catch {
      toast('임베딩 요청 중 오류가 발생했습니다.');
    }
  };

  return { submit, isSubmitting: syncMutation.isPending };
}
