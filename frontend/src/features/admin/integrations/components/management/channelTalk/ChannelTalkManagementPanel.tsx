'use client';

import IconAddSquare from '@/public/icons/icon/add_square.svg';
import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import { useChannelTalkViewModel } from '../../../hooks/useChannelTalkViewModel';
import type {
  ChannelTalkChannel,
  ChannelTalkChannelPatch,
  ChannelTalkConnectionState,
  ChannelTalkDocumentSpacePatch,
} from '../../../types/channelTalkModel';
import ChannelTalkChannelCard from './ChannelTalkChannelCard';

/** 채널톡 메인 패널 — 인터랙티브 mock state 자체 관리 (새로고침 시 초기화) */
export default function ChannelTalkManagementPanel() {
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
  } = useChannelTalkViewModel();

  const hasChannels = state.channels.length > 0;
  /** 데이터 범위 영역은 검증 통과(tested)한 채널이 있을 때만 활성 — 단순 채널 추가는 영향 없음 */
  const hasTestedChannels = state.channels.some((ch) => ch.connectionStatus === 'tested');
  const totalDocumentSpaces = state.channels.reduce((sum, ch) => sum + ch.documentSpaces.length, 0);

  return (
    <div className="flex flex-col gap-6">
      <ConnectionStatusSection state={state} />
      <DataRangeSection hasData={hasTestedChannels} />
      <CredentialSection
        channels={state.channels}
        channelCount={state.channels.length}
        totalDocumentSpaces={totalDocumentSpaces}
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
  state: ChannelTalkConnectionState;
}

/** 연동 상태 관리 — 연동 상태 토글 + 보안 관련 설명 */
function ConnectionStatusSection({ state }: ConnectionStatusSectionProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-content-normal">연동 상태 관리</h3>

      <div className="border-edge-assistive bg-fill-strong overflow-hidden rounded-xl border">
        <div className="border-edge-neutral flex items-center justify-between gap-8 border-b px-4 py-3">
          <span className="text-body-small text-content-normal">연동 상태</span>
          {state.connected ? (
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
  /** 검증(tested) 통과한 채널이 1개 이상일 때만 active 텍스트 표시 — 단순 채널 추가는 영향 없음 */
  hasData: boolean;
}

/** 연동된 데이터 범위 섹션 — tested 채널 없으면 placeholder */
function DataRangeSection({ hasData }: DataRangeSectionProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-content-neutral">연동된 데이터 범위</h3>
      <div
        className={cn(
          'border-edge-assistive bg-fill-strong text-body-small flex items-center justify-center overflow-hidden rounded-xl border px-4 py-3',
          hasData ? 'text-content-normal' : 'text-content-assistive',
        )}
      >
        <span className="truncate">
          {hasData ? '연동된 채널의 메시지를 임베딩하고 있어요.' : '연동되지 않았습니다.'}
        </span>
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
