'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import IconAddSquare from '@/public/icons/icon/add_square.svg';
import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import { useChannelTalkViewModel } from '../../../hooks/useChannelTalkViewModel';
import { channelTalkQueries } from '../../../queries/channelTalk.queries';
import type { ChannelTalkConnectionState } from '../../../types/channelTalkModel';
import type {
  ChannelTalkChannel,
  ChannelTalkChannelPatch,
  ChannelTalkDocumentSpacePatch,
} from '../../../types/channelTalkModel';
import type { ConnectorDetail } from '../../../types/integrationModel';
import { deriveChannelTalkInitialState } from '../../../utils/deriveChannelTalkInitialState';
import ChannelTalkChannelCard from './ChannelTalkChannelCard';

interface ChannelTalkManagementPanelProps {
  /** 다른 connector와 동일하게 백엔드 connector_target_status 기반 connected/dataRange 표시 */
  detail: ConnectorDetail;
}

/**
 * 채널톡 메인 패널.
 *
 * 외부 컴포넌트는 백엔드 GET 응답 fetch + 로딩 처리만 담당.
 * 데이터 ready 시 Inner를 mount하면서 deriveChannelTalkInitialState로 만든 initialState를 주입.
 * 이 mount/unmount 분리는 React 19 `react-hooks/set-state-in-effect` 룰을 회피하기 위함.
 */
export default function ChannelTalkManagementPanel({ detail }: ChannelTalkManagementPanelProps) {
  const channelListQuery = useQuery(channelTalkQueries.list());
  const documentListQuery = useQuery(channelTalkQueries.documentList());

  // outer가 detail 변화 등으로 자주 re-render돼도 derive 비용을 한 번만 지불.
  // TanStack Query는 동일 fetched data에 대해 stable reference를 보장하므로 cache hit이 잘 동작.
  const initialState = useMemo(
    () => deriveChannelTalkInitialState(channelListQuery.data, documentListQuery.data),
    [channelListQuery.data, documentListQuery.data],
  );

  if (channelListQuery.isLoading || documentListQuery.isLoading) {
    // 채널톡 백엔드 응답 대기 중 — 빈 placeholder. 짧은 폴링이라 별도 스켈레톤 없이 충분.
    return <div className="flex flex-col gap-6" />;
  }

  // fetch 실패 시 빈 카드로 무음 진입을 막아 "등록된 적 없음"으로 오인하는 것을 방지.
  // 사용자에게 명시적 에러 + 새로고침 안내. ConnectionStatus/DataRange 섹션 자리는 비워둠.
  if (channelListQuery.isError || documentListQuery.isError) {
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
    enterEditMode,
    addDocumentSpace,
    updateDocumentSpace,
    removeDocumentSpace,
    testChannelConnection,
    testDocumentSpaceConnection,
    enterDocumentSpaceEditMode,
  } = useChannelTalkViewModel(initialState);

  const hasChannels = state.channels.length > 0;
  /**
   * Credential 헤더 카운트("N개 채널 / N개 도큐먼트 연결됨")는 검증된(tested) 항목만 노출.
   * 사용자가 입력 중인 미검증 카드는 카운트에서 제외하여 "등록된 데이터" 의미를 유지.
   */
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

  // detail.connected: OAuth 설치 여부 / hasTestedChannels: credential 등록된 카드 표시용
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
        onEnterEditMode={enterEditMode}
        onAddDocumentSpace={addDocumentSpace}
        onUpdateDocumentSpace={updateDocumentSpace}
        onRemoveDocumentSpace={removeDocumentSpace}
        onEnterDocumentSpaceEditMode={enterDocumentSpaceEditMode}
        onTestChannelConnection={testChannelConnection}
        onTestDocumentSpaceConnection={testDocumentSpaceConnection}
      />
    </div>
  );
}

interface ConnectionStatusSectionProps {
  /** 검증 통과한 채널 1개 이상일 때 "연동됨" 표시 — `state.connected`와 분리된 파생값 */
  isConnected: boolean;
}

/** 연동 상태 관리 — 연동 상태 토글 + 보안 관련 설명 */
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

/**
 * 연동된 데이터 범위 섹션 — 다른 connector와 동일 동작.
 * `isConnected`가 true면 백엔드의 oldest~latest를 중앙 정렬로 표시, false면 placeholder를 좌측 정렬.
 */
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
  onEnterEditMode: (channelId: string) => void;
  onAddDocumentSpace: (channelId: string) => void;
  onUpdateDocumentSpace: (channelId: string, dsId: string, patch: ChannelTalkDocumentSpacePatch) => void;
  onRemoveDocumentSpace: (channelId: string, dsId: string) => void;
  onEnterDocumentSpaceEditMode: (channelId: string, dsId: string) => void;
  onTestChannelConnection: (channelId: string) => void;
  onTestDocumentSpaceConnection: (channelId: string, dsId: string) => void;
}

/** Credential Key 입력 및 동기화 주기 설정 — 채널 리스트 헤더 + 채널 카드들 */
function CredentialSection({
  channels,
  channelCount,
  totalDocumentSpaces,
  hasChannels,
  onAddChannel,
  onUpdateChannel,
  onRemoveChannel,
  onEnterEditMode,
  onAddDocumentSpace,
  onUpdateDocumentSpace,
  onRemoveDocumentSpace,
  onEnterDocumentSpaceEditMode,
  onTestChannelConnection,
  onTestDocumentSpaceConnection,
}: CredentialSectionProps) {
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-heading-small text-content-neutral">Credential Key 입력 및 동기화 주기 설정</h3>

      {hasChannels ? (
        <>
          {/* 채널 리스트 헤더 — 박스 전체가 "채널 추가하기" 클릭 영역 (default/hover/pressed 3상태) */}
          <AddChannelBox onClick={onAddChannel}>
            <span className="text-body-small text-content-normal shrink-0">{channelCount}개 채널</span>
            <span className="bg-dim-black-25 size-1 shrink-0 rounded-full" aria-hidden />
            <span className="text-body-small text-content-normal min-w-0 flex-1 truncate text-left">
              {totalDocumentSpaces}개 도큐먼트 연결됨
            </span>
          </AddChannelBox>

          {/* 채널 카드 리스트 */}
          <div className="flex flex-col gap-3">
            {channels.map((channel) => (
              <ChannelTalkChannelCard
                key={channel.id}
                channel={channel}
                onUpdate={(patch) => onUpdateChannel(channel.id, patch)}
                onRemove={() => onRemoveChannel(channel.id)}
                onEnterEdit={() => onEnterEditMode(channel.id)}
                onAddDocumentSpace={() => onAddDocumentSpace(channel.id)}
                onUpdateDocumentSpace={(dsId, patch) => onUpdateDocumentSpace(channel.id, dsId, patch)}
                onRemoveDocumentSpace={(dsId) => onRemoveDocumentSpace(channel.id, dsId)}
                onEnterDocumentSpaceEdit={(dsId) => onEnterDocumentSpaceEditMode(channel.id, dsId)}
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
  /** 자식과 우측 "채널 추가하기" 라벨 사이 간격 분기 — `between`은 placeholder 시, 기본은 채널 헤더용 */
  justify?: 'default' | 'between';
  children: React.ReactNode;
}

/** "채널 추가하기" 클릭 영역 박스 — 좌측 자식 컨텐츠 + 우측 고정 라벨 (default/hover/pressed 3상태) */
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
