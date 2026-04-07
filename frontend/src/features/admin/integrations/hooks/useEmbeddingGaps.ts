import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';

import { syncRecordGapsOptions } from '../queries/syncRecords.queries';
import type { AdminConnectorTargetRangeResponse, SyncRecordGapItem, SyncTargetStatus } from '../types/syncModel';

export interface GapSummary {
  eventId: string;
  attempt: number;
  eventStatus: SyncTargetStatus | null;
  totalMissing: number;
  totalExpected: number;
  totalStored: number;
  records: SyncRecordGapItem[];
}

/**
 * 실패한 target들의 gap 데이터를 병렬 조회.
 * 히스토리의 실패 항목에서 event_id를 추출하여 gap API를 호출한다.
 */
export const useEmbeddingGaps = (failedItems: AdminConnectorTargetRangeResponse[]) => {
  const targets = useMemo(() => failedItems.filter((item) => item.event_id), [failedItems]);

  const gapQueries = useQueries({
    queries: targets.map((item) => syncRecordGapsOptions(item.event_id)),
  });

  const gapByTargetId = useMemo((): Map<string, GapSummary> => {
    const map = new Map<string, GapSummary>();
    targets.forEach((item, i) => {
      const data = gapQueries[i]?.data;
      if (data) {
        const totalMissing = data.records.reduce((sum, r) => sum + r.missing_count, 0);
        const totalExpected = data.records.reduce((sum, r) => sum + r.expected_count, 0);
        const totalStored = data.records.reduce((sum, r) => sum + r.stored_count, 0);
        map.set(item.target_id, {
          eventId: item.event_id,
          attempt: data.attempt ?? 0,
          eventStatus: data.event_status,
          totalMissing,
          totalExpected,
          totalStored,
          records: data.records,
        });
      }
    });
    return map;
  }, [targets, gapQueries]);

  return {
    gapByTargetId,
    isLoading: gapQueries.some((q) => q.isLoading),
  };
};
