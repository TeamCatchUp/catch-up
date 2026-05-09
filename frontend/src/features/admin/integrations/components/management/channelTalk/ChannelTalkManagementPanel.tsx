'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import IconAddSquare from '@/public/icons/icon/add_square.svg';
import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import { useChannelTalkViewModel } from '../../../hooks/useChannelTalkViewModel';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import type { ChannelTalkConnectionState } from '../../../types/channelTalkModel';
import type {
  ChannelTalkChannel,
  ChannelTalkChannelPatch,
  ChannelTalkDocumentSpacePatch,
} from '../../../types/channelTalkModel';
import type { ChannelTalkConnectionStatusResponse } from '../../../types/connectionStatusApi';
import type { ConnectorDetail } from '../../../types/integrationModel';
import { deriveChannelTalkInitialState } from '../../../utils/deriveChannelTalkInitialState';
import ChannelTalkChannelCard from './ChannelTalkChannelCard';

interface ChannelTalkManagementPanelProps {
  // 백엔드 connector_target_status 기반 connected/dataRange
  detail: ConnectorDetail;
}

// 외부는 fetch + 로딩만, 데이터 ready 시 Inner mount하며 initialState 주입
export default function ChannelTalkManagementPanel({ detail }: ChannelTalkManagementPanelProps) {
  const statusQuery = useQuery(adminConnectorQueries.connectionStatus('channel_talk'));
  const channelTalkStatus =
    statusQuery.data?.vendor === 'channel_talk' ? (statusQuery.data as ChannelTalkConnectionStatusResponse) : undefined;

  // TanStack Query stable reference 덕분에 cache hit 시 derive 1회만 실행
  const initialState = useMemo(() => deriveChannelTalkInitialState(channelTalkStatus), [channelTalkStatus]);

  if (statusQuery.isLoading) {
    return <div className="flex flex-col gap-6" />;
  }

  // fetch 실패 시 "등록 없음"으로 오인 방지 — 명시적 에러 표시
  if (statusQuery.isError) {
    return (
      <div className="flex flex-col gap-6">
        <div className="border-edge-assistive bg-fill-strong text-body-small text-status-destructive rounded-xl border px-4 py-3">
          채널톡 연동 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
        </div>
      </div>
    );
  }

  return <ChannelTalkManagementPanelInner initialState={initialState} detail={detail} />;
}

interface ChannelTalkManagementPanelInnerProps {
  initialState: ChannelTalkConnectionState;
  detail: ConnectorDetail;
}

function ChannelTalkManagementPanelInner({ initialState, detail }: ChannelTalkManagementPanelInnerProps) {
  const {
    state,
    addChannel,
    updateChannel,
    removeChannel,
    addDocumentSpace,
    updateDocumentSpace,
    removeDocumentSpace,
    testChannelConnection,
    testDocumentSpaceConnection,
  } = useChannelTalkViewModel(initialState);

  const hasChannels = state.channels.length > 0;
  // 헤더 카운트는 tested만 — 미검증 카드는 "등록된 데이터" 정의에서 제외
  const { testedChannelCount, testedDocumentSpaceCount } = useMemo(() => {
    const testedChannels = state.channels.filter((ch) => ch.connectionStatus === 'tested');
    return {
      testedChannelCount: testedChannels.length,
      testedDocumentSpaceCount: testedChannels.reduce(
        (sum, ch) => sum + ch.documentSpaces.filter((ds) => ds.connectionStatus === 'tested').length,
        0,
      ),
    };
  }, [state.channels]);

  return (
    <div className="flex flex-col gap-6">
      <ConnectionStatusSection isConnected={detail.connected} />
      <DataRangeSection isConnected={detail.connected} dataRange={detail.dataRange} />
      <CredentialSection
        channels={state.channels}
        channelCount={testedChannelCount}
        totalDocumentSpaces={testedDocumentSpaceCount}
        hasChannels={hasChannels}
        onAddChannel={addChannel}
        onUpdateChannel={updateChannel}
        onRemoveChannel={removeChannel}
        onAddDocumentSpace={addDocumentSpace}
        onUpdateDocumentSpace={updateDocumentSpace}
        onRemoveDocumentSpace={removeDocumentSpace}
        onTestChannelConnection={testChannelConnection}
        onTestDocumentSpaceConnection={testDocumentSpaceConnection}
      />
    </div>
  );
}

interface ConnectionStatusSectionProps {
  // 검증 통과한 채널 1개 이상일 때 true (state.connected와 분리된 파생값)
  isConnected: boolean;
}

function ConnectionStatusSection({ isConnected }: ConnectionStatusSectionProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-content-normal">연동 상태 관리</h3>

      <div className="border-edge-assistive bg-fill-strong overflow-hidden rounded-xl border">
        <div className="border-edge-neutral flex items-center justify-between gap-8 border-b px-4 py-3">
          <span className="text-body-small text-content-normal">연동 상태</span>
          {isConnected ? (
            <div className="flex items-center gap-1 px-1.5 py-1">
              <IconCloudCheckFilled className="text-icon-primary-assistive size-4.5 shrink-0" />
              <span className="text-body-xsmall text-content-primary-assistive">연동됨</span>
            </div>
          ) : (
            <span className="text-body-xsmall text-content-alternative">연동 안됨</span>
          )}
        </div>
        <div className="flex items-center justify-between gap-8 px-4 py-3">
          <span className="text-body-small text-content-normal">보안 관련 설명</span>
          <Button variant="text-secondary-mono" size="sm" className="h-7">
            원문 보기
            <IconOpenInNew className="size-5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

interface DataRangeSectionProps {
  isConnected: boolean;
  dataRange: string;
}

// connected → 백엔드 oldest~latest 중앙 정렬, 미연결 → placeholder 좌측 정렬
function DataRangeSection({ isConnected, dataRange }: DataRangeSectionProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-content-neutral">연동된 데이터 범위</h3>
      <div
        className={cn(
          'border-edge-assistive bg-fill-strong text-body-small flex items-center overflow-hidden rounded-xl border px-4 py-3',
          isConnected ? 'text-content-normal justify-center' : 'text-content-assistive',
        )}
      >
        <span className="truncate">{isConnected ? dataRange : '연동되지 않았습니다.'}</span>
      </div>
    </div>
  );
}

interface CredentialSectionProps {
  channels: ChannelTalkChannel[];
  channelCount: number;
  totalDocumentSpaces: number;
  hasChannels: boolean;
  onAddChannel: () => void;
  onUpdateChannel: (channelId: string, patch: ChannelTalkChannelPatch) => void;
  onRemoveChannel: (channelId: string) => void;
  onAddDocumentSpace: (channelId: string) => void;
  onUpdateDocumentSpace: (channelId: string, dsId: string, patch: ChannelTalkDocumentSpacePatch) => void;
  onRemoveDocumentSpace: (channelId: string, dsId: string) => void;
  onTestChannelConnection: (channelId: string) => void;
  onTestDocumentSpaceConnection: (channelId: string, dsId: string) => void;
}

function CredentialSection({
  channels,
  channelCount,
  totalDocumentSpaces,
  hasChannels,
  onAddChannel,
  onUpdateChannel,
  onRemoveChannel,
  onAddDocumentSpace,
  onUpdateDocumentSpace,
  onRemoveDocumentSpace,
  onTestChannelConnection,
  onTestDocumentSpaceConnection,
}: CredentialSectionProps) {
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-heading-small text-content-neutral">Credential Key 입력 및 동기화 주기 설정</h3>

      {hasChannels ? (
        <>
          <AddChannelBox onClick={onAddChannel}>
            <span className="text-body-small text-content-normal shrink-0">{channelCount}개 채널</span>
            <span className="bg-dim-black-25 size-1 shrink-0 rounded-full" aria-hidden />
            <span className="text-body-small text-content-normal min-w-0 flex-1 truncate text-left">
              {totalDocumentSpaces}개 도큐먼트 연결됨
            </span>
          </AddChannelBox>

          <div className="flex flex-col gap-3">
            {channels.map((channel) => (
              <ChannelTalkChannelCard
                key={channel.id}
                channel={channel}
                onUpdate={(patch) => onUpdateChannel(channel.id, patch)}
                onRemove={() => onRemoveChannel(channel.id)}
                onAddDocumentSpace={() => onAddDocumentSpace(channel.id)}
                onUpdateDocumentSpace={(dsId, patch) => onUpdateDocumentSpace(channel.id, dsId, patch)}
                onRemoveDocumentSpace={(dsId) => onRemoveDocumentSpace(channel.id, dsId)}
                onTestConnection={() => onTestChannelConnection(channel.id)}
                onTestDocumentSpaceConnection={(dsId) => onTestDocumentSpaceConnection(channel.id, dsId)}
              />
            ))}
          </div>
        </>
      ) : (
        <AddChannelBox onClick={onAddChannel} justify="between">
          <span className="text-body-small text-content-assistive truncate">연동되지 않았습니다.</span>
        </AddChannelBox>
      )}
    </div>
  );
}

interface AddChannelBoxProps {
  onClick: () => void;
  // between → placeholder, default → 채널 헤더
  justify?: 'default' | 'between';
  children: React.ReactNode;
}

function AddChannelBox({ onClick, justify = 'default', children }: AddChannelBoxProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'border-edge-assistive bg-fill-strong hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed flex w-full cursor-pointer flex-wrap items-center gap-1.5 rounded-xl border px-4 py-3 transition-colors',
        justify === 'between' && 'justify-between',
      )}
    >
      {children}
      <span className="text-body-small text-content-primary flex shrink-0 items-center gap-2">
        <IconAddSquare className="text-icon-primary size-6 shrink-0" />
        채널 추가하기
      </span>
    </button>
  );
}
