import { useState } from 'react';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconClock from '@/public/icons/icon/clock.svg';
import IconClockPending from '@/public/icons/icon/clock_pending.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import IconInfo from '@/public/icons/icon/info.svg';
import IconProgress from '@/public/icons/icon/progress.svg';
import IconRotate from '@/public/icons/icon/rotate.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconTriangleUp from '@/public/icons/icon/triangle_up.svg';
import IconGithubLogo from '@/public/icons/logo/GitHub.svg';
import { cn } from '@/shared/utils/cn';

import { INTEGRATION_ACCOUNTS } from '../../../constants/integrations';
import type {
  AdminConnectorTargetRangeResponse,
  ConnectorProgress,
  EmbeddingButtonState,
  EmbeddingProgressItem,
  SyncConnector,
  SyncTargetStatus,
} from '../../../types/sync';

/** 서비스별 리소스 아이템 아이콘 (IntegrationManagementSection과 동일) */
const RESOURCE_ICONS: Record<SyncConnector, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  jira: IconSpace,
  github: IconGithubLogo,
  slack: IconTag,
  confluence: IconSpace,
};

/** "2026-03-05" → "2026.03.05 (수)" 포맷. 백엔드가 날짜만 반환하므로 시간 미표시. */
const formatHistoryDate = (dateStr: string): string => {
  // "YYYY-MM-DD" 형태를 직접 파싱하여 타임존 변환 방지
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const [y, m, d] = parts.map(Number);
  const date = new Date(y, m - 1, d);
  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const month = String(m).padStart(2, '0');
  const day = String(d).padStart(2, '0');
  return `${y}.${month}.${day} (${dayNames[date.getDay()]})`;
};

interface EmbeddingProgressPanelProps {
  progresses: ConnectorProgress[];
  buttonStates: Record<SyncConnector, EmbeddingButtonState>;
  isInitialLoading?: boolean;
  historyByConnector?: Partial<Record<SyncConnector, AdminConnectorTargetRangeResponse[]>>;
}

type ConnectorEmbeddingStatus = 'in_progress' | 'completed' | 'failed' | 'idle';

const CONNECTOR_ORDER: SyncConnector[] = ['jira', 'github', 'slack', 'confluence'];

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

const ItemStatusIcon = ({ status }: { status: SyncTargetStatus }) => {
  switch (status) {
    case 'success':
      return <IconCheckCircle className="text-accent-green size-6" />;
    case 'pending':
      return <IconClockPending className="text-status-cautionary size-6" />;
    case 'in_progress':
    case 'retrying':
      return <IconRotate className="text-content-primary size-6 animate-spin" />;
    case 'failed':
      return <IconDelete2 className="text-status-destructive size-6" />;
  }
};

const EmbeddingProgressPanel = ({ progresses, buttonStates, isInitialLoading, historyByConnector }: EmbeddingProgressPanelProps) => {
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

        {/* 본문: 좌측 칩 목록 + 우측 아이템 목록 */}
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

          {/* 우측: 선택된 커넥터의 아이템 목록 */}
          <div className="border-edge-assistive bg-fill-normal flex min-w-0 flex-1 overflow-hidden rounded-2xl border">
            <div className="thin-scrollbar flex max-h-56 flex-1 flex-col overflow-y-auto">
              {selectedProgress?.items.map((item: EmbeddingProgressItem) => {
                const ResourceIcon = RESOURCE_ICONS[selectedConnector];
                return (
                  <div
                    key={item.targetId}
                    className="border-edge-assistive flex h-14 shrink-0 items-center gap-4 border-b px-4 last:border-b-0"
                  >
                    <div className="border-edge-normal bg-fill-normal/75 flex shrink-0 items-center justify-center overflow-hidden rounded-full border p-1.5">
                      <ResourceIcon className="size-5" />
                    </div>
                    <span className="text-body-small text-content-normal flex-1 truncate">{item.displayName}</span>
                    <ItemStatusIcon status={item.status} />
                  </div>
                );
              })}
              {(!selectedProgress || selectedProgress.items.length === 0) && (
                <div className="flex flex-1 items-center justify-center px-4">
                  <span className="text-body-small text-content-assistive">
                    {isInitialLoading
                      ? '임베딩 상태를 불러오는 중...'
                      : buttonStates[selectedConnector] === 'in_progress'
                        ? '임베딩 정보를 불러오는 중...'
                        : '진행 중인 항목이 없습니다.'}
                  </span>
                </div>
              )}

              {/* 임베딩 히스토리 */}
              {historyByConnector?.[selectedConnector]?.length ? (
                <>
                  <div className="flex shrink-0 items-center px-5 pt-4 pb-1">
                    <span className="text-body-xsmall text-content-normal">임베딩 히스토리</span>
                  </div>
                  {historyByConnector[selectedConnector]!.map((item) => {
                    const ResourceIcon = RESOURCE_ICONS[selectedConnector];
                    return (
                      <div
                        key={`${item.scope_id}-${item.target_id}`}
                        className="border-edge-assistive flex h-14 shrink-0 items-center gap-4 border-b px-4 last:border-b-0"
                      >
                        <div className="border-edge-normal bg-fill-normal/75 flex shrink-0 items-center justify-center overflow-hidden rounded-full border p-1.5">
                          <ResourceIcon className="size-5" />
                        </div>
                        <span className="text-body-small text-content-normal flex-1 truncate">
                          {item.target_name}
                        </span>
                        {item.latest && (
                          <span className="text-label-xsmall text-content-alternative shrink-0 whitespace-nowrap">
                            {formatHistoryDate(item.latest)}
                          </span>
                        )}
                        <IconCheckCircle className="text-accent-green size-6 shrink-0" />
                      </div>
                    );
                  })}
                </>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmbeddingProgressPanel;
