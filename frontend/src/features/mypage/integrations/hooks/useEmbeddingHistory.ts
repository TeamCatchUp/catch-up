import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';

import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { AdminConnectorTargetRangeResponse, ConnectorStatusSource, SyncConnector } from '../types/sync';

const SOURCE_ORDER: ConnectorStatusSource[] = ['jira', 'github', 'slack', 'confluence'];

/**
 * 임베딩 히스토리 조회 훅.
 *
 * GET /admin/connector/status?source=X 를 4개 커넥터에 대해 병렬 호출.
 * target별 임베딩 데이터 범위(oldest~latest)를 반환.
 */
export const useEmbeddingHistory = () => {
  const historyQueries = useQueries({
    queries: SOURCE_ORDER.map((source) => adminConnectorQueries.connectorTargetStatus(source)),
  });

  const historyByConnector = useMemo((): Partial<Record<SyncConnector, AdminConnectorTargetRangeResponse[]>> => {
    const result: Partial<Record<SyncConnector, AdminConnectorTargetRangeResponse[]>> = {};
    SOURCE_ORDER.forEach((source, i) => {
      const targets = historyQueries[i]?.data?.targets;
      if (targets?.length) {
        // in_progress/pending은 진행 중 섹션(useEmbeddingJobs)에서 표시하므로 제외
        const completed = targets.filter((t) => t.sync_status !== 'in_progress' && t.sync_status !== 'pending');
        if (completed.length) {
          result[source as SyncConnector] = completed;
        }
      }
    });
    return result;
  }, [historyQueries]);

  return {
    historyByConnector,
    isLoading: historyQueries.some((q) => q.isLoading),
  };
};
