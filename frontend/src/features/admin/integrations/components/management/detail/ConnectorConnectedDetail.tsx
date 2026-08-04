'use client';

import { useMemo, useState } from 'react';

import { Button } from '@/shared/components/ui/button';

import { CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import { useEmbeddingGaps } from '../../../hooks/useEmbeddingGaps';
import { useEmbeddingHistory } from '../../../hooks/useEmbeddingHistory';
import { useEmbeddingJobs } from '../../../hooks/useEmbeddingJobs';
import { useSyncRecordRetry } from '../../../queries/syncRecords.mutations';
import type { ConnectorDetail, IntegrationService } from '../../../types/integrationModel';
import type { AdminConnectorTargetRangeResponse } from '../../../types/syncModel';
import { formatHistoryDate } from '../../../utils/embeddingUtils';
import EmbeddingModal from '../../member/modals/EmbeddingModal';
import EmbeddingRetryModal from '../../member/modals/EmbeddingRetryModal';
import ConnectorSummaryCard from '../cards/ConnectorSummaryCard';
import EmbeddedResourceTable from '../embedding/EmbeddedResourceTable';
import EmbeddingActiveTable from '../embedding/EmbeddingActiveTable';
import EmbeddingHistoryTable, { type EmbeddingHistoryItem } from '../embedding/EmbeddingHistoryTable';
import EmbeddingSegmentTabs, { type EmbeddingTabValue } from '../embedding/EmbeddingSegmentTabs';
import ConnectorDetailHeader from './ConnectorDetailHeader';

interface ConnectorConnectedDetailProps {
  service: IntegrationService;
  detail: ConnectorDetail;
  /** 채널톡 [임베딩 추가] — (F) 2스텝으로 전환. 다른 도구는 임베딩 모달을 연다 */
  onEnterChannelTalkFlow: () => void;
}

/**
 * (E) 커넥터 상세 — 연동됨. 스펙 §5-3, Figma `17306:82016`.
 * 헤더 + 세그먼트 탭 + [관리: 요약 카드 + 대상 표 | 현황: 진행중 표 + 히스토리].
 *
 * 헤더 제목은 스펙상 워크스페이스명인데 API가 주지 않아 도구명으로 둔다(미결 — 백엔드).
 * 재시도 흐름(gap 조회 → EmbeddingRetryModal → useSyncRecordRetry)은
 * 구 `EmbeddingHistoryCard`의 것을 그대로 옮겼다.
 */
export default function ConnectorConnectedDetail({
  service,
  detail,
  onEnterChannelTalkFlow,
}: ConnectorConnectedDetailProps) {
  const content = CONNECTOR_CONTENT[service];
  const [tab, setTab] = useState<EmbeddingTabValue>('manage');
  const [embeddingModalOpen, setEmbeddingModalOpen] = useState(false);
  const [retryTarget, setRetryTarget] = useState<AdminConnectorTargetRangeResponse | null>(null);

  // 진행중 — 이 서비스의 활성 job에 속한 target들
  const { progresses, handleJobStart } = useEmbeddingJobs();
  const activeItems = useMemo(() => {
    /*
     * job의 items에는 그 job의 **모든** target이 상태와 함께 들어 있다.
     * 완료된 것까지 넘기면 전부 "진행중"으로 표시되므로 미완료만 거른다
     * (구 EmbeddingProgressPanel:111 과 같은 필터).
     *
     * 그리고 한 커넥터에 job이 여럿일 수 있어(채널톡 multi-channel, 같은 도구
     * 재실행) target이 중복된다 — targetId로 dedupe 하지 않으면 표에 같은 줄이
     * 두 번 나오고 React key 도 충돌한다.
     */
    const seen = new Map<string, { id: string; target: string }>();
    for (const progress of progresses) {
      if (progress.connector !== service) continue;
      for (const item of progress.items) {
        if (item.status !== 'pending' && item.status !== 'in_progress' && item.status !== 'retrying') continue;
        if (!seen.has(item.targetId)) seen.set(item.targetId, { id: item.targetId, target: item.displayName });
      }
    }
    return [...seen.values()];
  }, [progresses, service]);

  // 히스토리 — 완료(success/failed) target들
  const { historyByConnector } = useEmbeddingHistory();
  const historyItems = useMemo(() => historyByConnector[service] ?? [], [historyByConnector, service]);
  const failedItems = useMemo(() => historyItems.filter((item) => item.sync_status === 'failed'), [historyItems]);
  const { gapByTargetId } = useEmbeddingGaps(failedItems);

  const historyRows: EmbeddingHistoryItem[] = useMemo(
    () =>
      historyItems.map((item) => {
        const failed = item.sync_status === 'failed';
        return {
          id: `${item.scope_id}-${item.target_id}`,
          target: item.target_name,
          status: failed ? ('failed' as const) : ('success' as const),
          executedAt: formatHistoryDate((failed ? item.last_failed_at : item.last_succeeded_at) ?? ''),
          failureCount: failed ? gapByTargetId.get(item.target_id)?.totalMissing : undefined,
        };
      }),
    [historyItems, gapByTargetId],
  );

  // 재시도 — 구 EmbeddingHistoryCard의 흐름 그대로
  const retryMutation = useSyncRecordRetry();
  const retryGap = retryTarget ? gapByTargetId.get(retryTarget.target_id) : undefined;

  const handleRetryConfirm = () => {
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

  const handleAddEmbedding = () => {
    if (service === 'channel_talk') onEnterChannelTalkFlow();
    else setEmbeddingModalOpen(true);
  };

  return (
    <div className="flex flex-col gap-6">
      <ConnectorDetailHeader
        service={service}
        title={content.name}
        description={content.headerDescription}
        actions={
          <Button variant="box-solid-primary" size="md" onClick={handleAddEmbedding}>
            임베딩 추가
          </Button>
        }
      />

      <EmbeddingSegmentTabs value={tab} hasRunning={activeItems.length > 0} onChange={setTab} />

      {tab === 'manage' ? (
        <div className="flex flex-col gap-6">
          <ConnectorSummaryCard
            connected={detail.connected}
            dataRange={detail.dataRange === '-' ? null : detail.dataRange}
          />
          {/*
           * 채널톡의 채널→도큐먼트 계층은 이 API(connector/status targets)가 평면으로만
           * 줘서 아직 살리지 못한다 — 계층 응답이 생기면 children으로 매핑한다(미결)
           */}
          <EmbeddedResourceTable
            service={service}
            label={detail.resourceLabel}
            rows={detail.resources.map((r, i) => ({ id: `${r.name}-${i}`, name: r.name, dataRange: r.dateRange ?? '-' }))}
          />
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          <EmbeddingActiveTable service={service} items={activeItems} />
          <EmbeddingHistoryTable
            service={service}
            items={historyRows}
            onRetry={(id) => {
              const item = historyItems.find((h) => `${h.scope_id}-${h.target_id}` === id);
              if (item) setRetryTarget(item);
            }}
          />
        </div>
      )}

      {service !== 'channel_talk' && (
        <EmbeddingModal
          open={embeddingModalOpen}
          onOpenChange={setEmbeddingModalOpen}
          service={service}
          serviceName={content.name}
          onJobStart={handleJobStart}
        />
      )}

      <EmbeddingRetryModal
        open={!!retryTarget}
        onOpenChange={(open) => {
          if (!open && !retryMutation.isPending) setRetryTarget(null);
        }}
        targetName={retryTarget?.target_name ?? ''}
        totalCount={retryGap?.totalExpected ?? 0}
        successCount={retryGap?.totalStored ?? 0}
        failedCount={retryGap?.totalMissing ?? 0}
        retryAttempt={retryGap?.attempt ?? 0}
        isLoading={retryMutation.isPending}
        onConfirm={handleRetryConfirm}
      />
    </div>
  );
}
