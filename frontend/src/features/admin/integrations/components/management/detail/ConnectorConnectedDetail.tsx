'use client';

import { useMemo, useState } from 'react';

import { Button } from '@/shared/components/ui/button';

import { CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import { useEmbeddingHistory } from '../../../hooks/useEmbeddingHistory';
import { useEmbeddingJobs } from '../../../hooks/useEmbeddingJobs';
import { useEmbeddingRetry } from '../../../hooks/useEmbeddingRetry';
import type { ConnectorDetail, ConnectorResource, IntegrationService } from '../../../types/integrationModel';
import { formatHistoryDate } from '../../../utils/embeddingUtils';
import ConnectorSummaryCard from '../cards/ConnectorSummaryCard';
import EmbeddedResourceTable, { type EmbeddedResourceRow } from '../embedding/EmbeddedResourceTable';
import EmbeddingActiveTable from '../embedding/EmbeddingActiveTable';
import EmbeddingHistoryTable, { type EmbeddingHistoryItem } from '../embedding/EmbeddingHistoryTable';
import EmbeddingSegmentTabs, { type EmbeddingTabValue } from '../embedding/EmbeddingSegmentTabs';
import EmbeddingModal from '../modals/EmbeddingModal';
import EmbeddingRetryModal from '../modals/EmbeddingRetryModal';
import ConnectorDetailHeader from './ConnectorDetailHeader';

interface ConnectorConnectedDetailProps {
  service: IntegrationService;
  detail: ConnectorDetail;
  /** 채널톡 [임베딩 추가] — (F) 2스텝으로 전환. 다른 도구는 임베딩 모달을 연다 */
  onEnterChannelTalkFlow: () => void;
}

/**
 * (E) 커넥터 상세 — 연동됨. 스펙 §5-3.
 * 헤더 + 세그먼트 탭 + [관리: 요약 카드 + 대상 표 | 현황: 진행중 표 + 히스토리].
 * 헤더 제목은 연동된 조직·워크스페이스의 대표 이름이다(connection-status `items[].name`).
 */
export default function ConnectorConnectedDetail({
  service,
  detail,
  onEnterChannelTalkFlow,
}: ConnectorConnectedDetailProps) {
  const content = CONNECTOR_CONTENT[service];
  const [tab, setTab] = useState<EmbeddingTabValue>('manage');
  const [embeddingModalOpen, setEmbeddingModalOpen] = useState(false);

  /*
   * 뷰모델의 리소스 트리 → 표 행. 채널톡은 채널 아래 도큐먼트 스페이스가 children으로
   * 달려 오고(useAdminIntegrationViewModel → buildChannelTalkResourceTree), 나머지
   * 도구는 children이 없어 평면 그대로다.
   */
  const resourceRows = useMemo(() => {
    const toRow = (r: ConnectorResource): EmbeddedResourceRow => ({
      id: r.id,
      name: r.name,
      dataRange: r.dateRange ?? '-',
      children: r.children?.map(toRow),
    });
    return detail.resources.map(toRow);
  }, [detail.resources]);

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

  // 히스토리 — 완료(success/failed) target들. 재시도 흐름은 useEmbeddingRetry가 담당
  const { historyByConnector } = useEmbeddingHistory();
  const historyItems = useMemo(() => historyByConnector[service] ?? [], [historyByConnector, service]);
  const failedItems = useMemo(() => historyItems.filter((item) => item.sync_status === 'failed'), [historyItems]);
  const retry = useEmbeddingRetry(failedItems);

  const historyRows: EmbeddingHistoryItem[] = useMemo(
    () =>
      historyItems.map((item) => {
        const failed = item.sync_status === 'failed';
        return {
          id: `${item.scope_id}-${item.target_id}`,
          target: item.target_name,
          status: failed ? ('failed' as const) : ('success' as const),
          executedAt: formatHistoryDate((failed ? item.last_failed_at : item.last_succeeded_at) ?? ''),
          failureCount: failed ? retry.gapByTargetId.get(item.target_id)?.totalMissing : undefined,
        };
      }),
    [historyItems, retry.gapByTargetId],
  );

  /*
   * 헤더 액션은 도구에 따라 다르다(Figma 실측).
   *   채널톡  "채널 연결하기" → (F) 스텝 ① 채널 연결 관리
   *   그 외    "임베딩 추가"   → 임베딩 모달
   * 채널톡은 채널 credential 등록이 선행이라 임베딩 단계로 바로 보내지 않는다.
   */
  const isChannelTalk = service === 'channel_talk';
  const actionLabel = isChannelTalk ? '채널 연결하기' : '임베딩 추가';

  const handleHeaderAction = () => {
    if (isChannelTalk) onEnterChannelTalkFlow();
    else setEmbeddingModalOpen(true);
  };

  return (
    <div className="flex flex-col gap-6">
      <ConnectorDetailHeader
        service={service}
        // 헤더 제목은 연동된 조직·워크스페이스 대표 이름 — 백엔드가 null이면 도구명으로 폴백
        title={detail.workspaceName ?? content.name}
        description={content.headerDescription}
        actions={
          <Button variant="box-solid-primary" size="lg" onClick={handleHeaderAction}>
            {actionLabel}
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
          <EmbeddedResourceTable service={service} label={detail.resourceLabel} rows={resourceRows} />
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          <EmbeddingActiveTable service={service} items={activeItems} />
          <EmbeddingHistoryTable
            service={service}
            items={historyRows}
            onRetry={(id) => {
              const item = historyItems.find((h) => `${h.scope_id}-${h.target_id}` === id);
              if (item) retry.openRetryModal(item);
            }}
          />
        </div>
      )}

      {!isChannelTalk && (
        <EmbeddingModal
          open={embeddingModalOpen}
          onOpenChange={setEmbeddingModalOpen}
          service={service}
          serviceName={content.name}
          onJobStart={handleJobStart}
        />
      )}

      <EmbeddingRetryModal
        open={!!retry.retryTarget}
        onOpenChange={retry.handleModalOpenChange}
        targetName={retry.retryTarget?.target_name ?? ''}
        totalCount={retry.retryGap?.totalExpected ?? 0}
        successCount={retry.retryGap?.totalStored ?? 0}
        failedCount={retry.retryGap?.totalMissing ?? 0}
        retryAttempt={retry.retryGap?.attempt ?? 0}
        isLoading={retry.isRetrying}
        onConfirm={retry.confirmRetry}
      />
    </div>
  );
}
