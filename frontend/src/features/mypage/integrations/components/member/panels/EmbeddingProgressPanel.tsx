import { useState } from 'react';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconClock from '@/public/icons/icon/clock.svg';
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
import type { ConnectorProgress, EmbeddingProgressItem, SyncConnector, SyncJobStatus } from '../../../types/sync';

/** 서비스별 리소스 아이템 아이콘 (IntegrationManagementSection과 동일) */
const RESOURCE_ICONS: Record<SyncConnector, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  jira: IconSpace,
  github: IconGithubLogo,
  slack: IconTag,
  confluence: IconSpace,
};

interface EmbeddingProgressPanelProps {
  progresses: ConnectorProgress[];
}

type ConnectorEmbeddingStatus = 'in_progress' | 'completed' | 'idle';

const CONNECTOR_ORDER: SyncConnector[] = ['jira', 'github', 'slack', 'confluence'];

const getConnectorStatus = (
  connector: SyncConnector,
  progresses: ConnectorProgress[],
): ConnectorEmbeddingStatus => {
  const progress = progresses.find((p) => p.connector === connector);
  if (!progress) return 'idle';
  if (progress.status === 'success') return 'completed';
  return 'in_progress';
};

const getConnectorStatusLabel = (status: ConnectorEmbeddingStatus) => {
  switch (status) {
    case 'in_progress':
      return '임베딩 진행 중';
    case 'completed':
      return '임베딩 완료';
    case 'idle':
      return '임베딩 전';
  }
};

const ConnectorStatusIcon = ({
  status,
  isSelected,
}: {
  status: ConnectorEmbeddingStatus;
  isSelected: boolean;
}) => {
  switch (status) {
    case 'in_progress':
      return (
        <IconRotate
          className={cn(
            'size-4.5',
            isSelected ? 'text-edge-primary-strong' : 'text-content-assistive',
          )}
        />
      );
    case 'completed':
      return (
        <IconCheckCircle
          className={cn('size-4.5', isSelected ? 'text-accent-green' : 'text-content-assistive')}
        />
      );
    case 'idle':
      return (
        <IconClock
          className={cn(
            'size-4.5',
            isSelected ? 'text-status-cautionary' : 'text-content-assistive',
          )}
        />
      );
  }
};

const ItemStatusIcon = ({ status }: { status: SyncJobStatus }) => {
  switch (status) {
    case 'success':
      return <IconCheckCircle className="size-6 text-accent-green" />;
    case 'in_progress':
    case 'pending':
      return <IconRotate className="size-6 animate-spin text-content-primary" />;
    case 'failed':
      return <IconDelete2 className="size-6 text-status-destructive" />;
  }
};

const EmbeddingProgressPanel = ({ progresses }: EmbeddingProgressPanelProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [hasAutoOpened, setHasAutoOpened] = useState(false);

  const [selectedConnector, setSelectedConnector] = useState<SyncConnector>(
    CONNECTOR_ORDER.find((c) => progresses.some((p) => p.connector === c)) ?? CONNECTOR_ORDER[0],
  );

  // 진행 중인 job이 처음 감지되면 자동으로 펼침 + 활성 커넥터 선택 (렌더 중 1회)
  if (progresses.length > 0 && !hasAutoOpened) {
    setHasAutoOpened(true);
    if (!isOpen) setIsOpen(true);
    const first = CONNECTOR_ORDER.find((c) => progresses.some((p) => p.connector === c));
    if (first && first !== selectedConnector) setSelectedConnector(first);
  }

  const selectedProgress = progresses.find((p) => p.connector === selectedConnector);

  // 접힌 상태: 토글 바
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="flex w-full cursor-pointer items-center gap-4 rounded-xl border border-edge-assistive bg-fill-strong px-4 py-2.5"
      >
        <IconProgress className="size-5 text-content-normal" />
        <span className="text-body-small flex-1 text-left text-content-normal">임베딩 진행 현황 보기</span>
        <IconArrowDown className="size-6 text-content-assistive" />
      </button>
    );
  }

  // 펼친 상태: 말풍선 삼각형 + 패널 본체
  return (
    <div className="flex flex-col items-center">
      <IconTriangleUp className="h-3.75 w-7 shrink-0 text-fill-interaction-hover" />
      <div className="flex w-full flex-col gap-4 rounded-2xl bg-fill-interaction-hover p-5">
        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 px-1.5">
            <h3 className="text-heading-small text-content-normal">임베딩 진행 현황</h3>
            <IconInfo className="size-4.5 text-content-assistive" />
          </div>
          <button onClick={() => setIsOpen(false)} className="cursor-pointer p-1">
            <IconArrowDown className="size-6 rotate-180 text-content-assistive" />
          </button>
        </div>

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
                    className={cn(
                      'text-body-xsmall',
                      isSelected ? 'text-content-primary' : 'text-content-assistive',
                    )}
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
        <div className="flex min-w-0 flex-1 overflow-hidden rounded-2xl border border-edge-assistive bg-fill-normal">
          <div className="thin-scrollbar flex max-h-56 flex-1 flex-col overflow-y-auto">
            {selectedProgress?.items.map((item: EmbeddingProgressItem) => {
              const ResourceIcon = RESOURCE_ICONS[selectedConnector];
              return (
                <div
                  key={item.targetId}
                  className="flex h-14 shrink-0 items-center gap-4 border-b border-edge-assistive px-4 last:border-b-0"
                >
                  {/* 리소스 아이콘 */}
                  <div className="flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-edge-normal bg-fill-normal/75 p-1.5">
                    <ResourceIcon className="size-5" />
                  </div>
                  {/* 항목명 */}
                  <span className="text-body-small flex-1 truncate text-content-normal">
                    {item.displayName}
                  </span>
                  {/* 상태 아이콘 */}
                  <ItemStatusIcon status={item.status} />
                </div>
              );
            })}
            {(!selectedProgress || selectedProgress.items.length === 0) && (
              <div className="flex flex-1 items-center justify-center px-4">
                <span className="text-body-small text-content-assistive">진행 중인 항목이 없습니다.</span>
              </div>
            )}
          </div>
        </div>
      </div>
      </div>
    </div>
  );
};

export default EmbeddingProgressPanel;
