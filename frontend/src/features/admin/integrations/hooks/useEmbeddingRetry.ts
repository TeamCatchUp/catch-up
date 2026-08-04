'use client';

import { useState } from 'react';

import { useSyncRecordRetry } from '../queries/syncRecords.mutations';
import type { AdminConnectorTargetRangeResponse } from '../types/syncModel';
import { useEmbeddingGaps } from './useEmbeddingGaps';

/**
 * 실패한 임베딩 target의 재시도 흐름 — gap 조회, 확인 모달 상태, 재시도 mutation.
 * `ConnectorConnectedDetail`에서 추출했다. 모달은 재시도 진행 중에는 닫히지 않는다.
 */
export function useEmbeddingRetry(failedItems: AdminConnectorTargetRangeResponse[]) {
  const { gapByTargetId } = useEmbeddingGaps(failedItems);
  const retryMutation = useSyncRecordRetry();
  const [retryTarget, setRetryTarget] = useState<AdminConnectorTargetRangeResponse | null>(null);

  const retryGap = retryTarget ? gapByTargetId.get(retryTarget.target_id) : undefined;

  const confirmRetry = () => {
    if (!retryTarget || !retryGap) return;
    retryMutation.mutate(
      {
        event_id: retryGap.eventId,
        records: retryGap.records
          .filter((r) => r.missing_count > 0)
          .map((r) => ({ record_type: r.record_type, record_ids: r.missing_ids })),
      },
      { onSuccess: () => setRetryTarget(null) },
    );
  };

  const handleModalOpenChange = (open: boolean) => {
    if (!open && !retryMutation.isPending) setRetryTarget(null);
  };

  return {
    gapByTargetId,
    retryTarget,
    retryGap,
    isRetrying: retryMutation.isPending,
    openRetryModal: setRetryTarget,
    confirmRetry,
    handleModalOpenChange,
  };
}
