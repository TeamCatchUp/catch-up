import { useState } from 'react';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconClock from '@/public/icons/icon/clock.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import IconInfo from '@/public/icons/icon/info.svg';
import IconProgress from '@/public/icons/icon/progress.svg';
import IconRotate from '@/public/icons/icon/rotate.svg';
import IconTriangleUp from '@/public/icons/icon/triangle_up.svg';
import { cn } from '@/shared/utils/cn';

import { CONNECTOR_ORDER } from '../../../constants/connectorOrder';
import { INTEGRATION_ACCOUNTS } from '../../../constants/integrationsConfig';
import { useEmbeddingGaps } from '../../../hooks/useEmbeddingGaps';
import type {
  AdminConnectorTargetRangeResponse,
  ConnectorProgress,
  EmbeddingButtonState,
  SyncConnector,
} from '../../../types/syncModel';
import EmbeddingActiveCard from './EmbeddingActiveCard';
import EmbeddingHistoryCard from './EmbeddingHistoryCard';

interface EmbeddingProgressPanelProps {
  progresses: ConnectorProgress[];
  buttonStates: Record<SyncConnector, EmbeddingButtonState>;
  isInitialLoading?: boolean;
  historyByConnector?: Partial<Record<SyncConnector, AdminConnectorTargetRangeResponse[]>>;
}

type ConnectorEmbeddingStatus = 'in_progress' | 'completed' | 'failed' | 'idle';

const getConnectorStatus = (connector: SyncConnector, progresses: ConnectorProgress[]): ConnectorEmbeddingStatus => {
  const progress = progresses.find((p) => p.connector === connector);
  if (!progress) return 'idle';
  if (progress.status === 'success') return 'completed';
  if (progress.status === 'failed') return 'failed';
  return 'in_progress';
};

const getConnectorStatusLabel = (status: ConnectorEmbeddingStatus) => {
  switch (status) {
    case 'in_progress':
      return '임베딩 진행 중';
    case 'completed':
      return '임베딩 완료';
    case 'failed':
      return '임베딩 실패';
    case 'idle':
      return '임베딩 전';
  }
};

const ConnectorStatusIcon = ({ status, isSelected }: { status: ConnectorEmbeddingStatus; isSelected: boolean }) => {
  switch (status) {
    case 'in_progress':
      return (
        <IconRotate className={cn('size-4.5', isSelected ? 'text-edge-primary-strong' : 'text-content-assistive')} />
      );
    case 'completed':
      return (
        <IconCheckCircle className={cn('size-4.5', isSelected ? 'text-accent-green' : 'text-content-assistive')} />
      );
    case 'failed':
      return (
        <IconDelete2 className={cn('size-4.5', isSelected ? 'text-status-destructive' : 'text-content-assistive')} />
      );
    case 'idle':
      return <IconClock className={cn('size-4.5', isSelected ? 'text-status-cautionary' : 'text-content-assistive')} />;
  }
};

export default function EmbeddingProgressPanel({
  progresses,
  buttonStates,
  isInitialLoading,
  historyByConnector,
}: EmbeddingProgressPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedConnector, setSelectedConnector] = useState<SyncConnector>(
    CONNECTOR_ORDER.find((c) => progresses.some((p) => p.connector === c)) ?? CONNECTOR_ORDER[0],
  );

  // 커넥터가 in_progress로 전환되면 자동으로 펼침 + 해당 커넥터 선택
  const [lastSeenInProgress, setLastSeenInProgress] = useState('');
  const currentInProgress = CONNECTOR_ORDER.filter((c) => buttonStates[c] === 'in_progress').join(',');

  if (currentInProgress !== lastSeenInProgress) {
    const prevSet = new Set(lastSeenInProgress ? lastSeenInProgress.split(',') : []);
    for (const connector of CONNECTOR_ORDER) {
      if (buttonStates[connector] === 'in_progress' && !prevSet.has(connector)) {
        if (!isOpen) setIsOpen(true);
        if (selectedConnector !== connector) setSelectedConnector(connector);
        break;
      }
    }
    setLastSeenInProgress(currentInProgress);
  }

  const selectedProgress = progresses.find((p) => p.connector === selectedConnector);
  const activeItems =
    selectedProgress?.items.filter(
      (item) => item.status === 'pending' || item.status === 'in_progress' || item.status === 'retrying',
    ) ?? [];
  const historyItems = historyByConnector?.[selectedConnector] ?? [];
  const failedItems = historyItems.filter((item) => item.sync_status === 'failed');
  const { gapByTargetId } = useEmbeddingGaps(failedItems);

  // 접힌 상태: 토글 바
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="border-edge-assistive bg-fill-strong flex w-full cursor-pointer items-center gap-4 rounded-xl border px-4 py-2.5"
      >
        <IconProgress className="text-content-normal size-5" />
        <span className="text-body-small text-content-normal flex-1 text-left">임베딩 진행 현황 보기</span>
        <IconArrowDown className="text-content-assistive size-6" />
      </button>
    );
  }

  // 펼친 상태: 말풍선 삼각형 + 패널 본체
  return (
    <div className="flex animate-[panel-slide-down_250ms_ease-out] flex-col items-center">
      <IconTriangleUp className="text-fill-interaction-hover h-3.75 w-7 shrink-0" />
      <div className="bg-fill-interaction-hover flex w-full flex-col gap-4 rounded-2xl p-5">
        {/* 헤더 */}
        <button onClick={() => setIsOpen(false)} className="flex w-full cursor-pointer items-center justify-between">
          <div className="flex items-center gap-1.5 px-1.5">
            <h3 className="text-heading-small text-content-normal">임베딩 진행 현황</h3>
            <IconInfo className="text-content-assistive size-4.5" />
          </div>
          <div className="p-1">
            <IconArrowDown className="text-content-assistive size-6 rotate-180" />
          </div>
        </button>

        {/* 본문: 좌측 칩 목록 + 우측 카드 영역 */}
        <div className="flex gap-14">
          {/* 좌측: 커넥터 칩 목록 */}
          <div className="flex shrink-0 flex-col gap-2.5">
            {CONNECTOR_ORDER.map((connector) => {
              const account = INTEGRATION_ACCOUNTS.find((a) => a.service === connector);
              const status = getConnectorStatus(connector, progresses);
              const isSelected = connector === selectedConnector;

              return (
                <button
                  key={connector}
                  onClick={() => setSelectedConnector(connector)}
                  className={cn(
                    'flex h-12 w-58.5 cursor-pointer items-center gap-6 overflow-hidden rounded-full border px-5 py-2.5',
                    isSelected
                      ? 'border-edge-primary bg-fill-primary-normal-neutral'
                      : 'border-edge-neutral bg-fill-normal',
                  )}
                >
                  <span
                    className={cn(
                      'text-body-small flex-1 text-left',
                      isSelected ? 'text-content-primary' : 'text-content-neutral',
                    )}
                  >
                    {account?.name ?? connector}
                  </span>
                  <div className="flex items-center gap-1">
                    <span
                      className={cn('text-body-xsmall', isSelected ? 'text-content-primary' : 'text-content-assistive')}
                    >
                      {getConnectorStatusLabel(status)}
                    </span>
                    <ConnectorStatusIcon status={status} isSelected={isSelected} />
                  </div>
                </button>
              );
            })}
          </div>

          {/* 우측: 두 개의 독립 카드 */}
          <div className="flex min-w-0 flex-1 flex-col gap-2.5">
            {activeItems.length > 0 && <EmbeddingActiveCard items={activeItems} connector={selectedConnector} />}
            <EmbeddingHistoryCard
              items={historyItems}
              connector={selectedConnector}
              isInitialLoading={isInitialLoading}
              gapByTargetId={gapByTargetId}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
