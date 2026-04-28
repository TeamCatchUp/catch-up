'use client';

import IconAdd from '@/public/icons/icon/add.svg';
import IconMegaphone from '@/public/icons/icon/megaphone.svg';
import IconTag from '@/public/icons/icon/tag.svg';

import type { ChannelTalkChannel, ChannelTalkConnectionStatus } from '../../../types/channelTalkModel';
import ChannelTalkConnectionTestButton from './ChannelTalkConnectionTestButton';
import ChannelTalkDocumentSpaceCard from './ChannelTalkDocumentSpaceCard';
import ChannelTalkSyncIntervalDropdown from './ChannelTalkSyncIntervalDropdown';
import ChannelTalkTextField from './ChannelTalkTextField';

const MEGAPHONE_NOTICE =
  '채널은 실시간으로 문의가 들어오는 공간이에요. 주기를 짧게 설정할수록 최신 대화가 반영되어 답변 품질이 좋아져요.';

type FieldState = 'idle' | 'error' | 'focus';
type TestButtonStatus = 'idle' | 'active' | 'success';
type ChannelFieldName = 'accessKey' | 'accessSecret' | 'webhookToken';

/**
 * connectionStatus → 각 textfield의 시각 변형 매핑.
 * - error: 모든 필드 destructive border
 * - editing: Access Key만 focus border (사용자 수정 중), 나머지는 idle
 * - 그 외 (idle/entered/tested): 모두 idle
 */
function fieldStateFor(status: ChannelTalkConnectionStatus, fieldName: ChannelFieldName): FieldState {
  if (status === 'error') return 'error';
  if (status === 'editing' && fieldName === 'accessKey') return 'focus';
  return 'idle';
}

/** connectionStatus → 연결 테스트 버튼 상태 매핑 */
function testButtonStatusFor(status: ChannelTalkConnectionStatus): TestButtonStatus {
  if (status === 'tested') return 'success';
  if (status === 'editing') return 'active';
  return 'idle';
}

interface ChannelTalkChannelCardProps {
  channel: ChannelTalkChannel;
  onAddDocumentSpace?: () => void;
}

/** 채널톡 채널 카드 — connectionStatus(idle/entered/tested/error/editing)에 따라 5변형 렌더 */
export default function ChannelTalkChannelCard({ channel, onAddDocumentSpace }: ChannelTalkChannelCardProps) {
  const status = channel.connectionStatus;
  const accessKeyState = fieldStateFor(status, 'accessKey');
  const accessSecretState = fieldStateFor(status, 'accessSecret');
  const webhookTokenState = fieldStateFor(status, 'webhookToken');
  const testStatus = testButtonStatusFor(status);

  return (
    <div className="border-edge-neutral bg-fill-normal relative flex flex-col overflow-hidden rounded-xl border">
      {/* 헤더 행 좌측 파란색 indicator strip — tag icon 영역 높이(32px)와 동일 */}
      <div className="bg-edge-primary-strong absolute top-4 left-0 h-8 w-1" aria-hidden />

      {/* Vertical input form (684×340 영역) */}
      <div className="flex flex-col gap-4 px-4 pt-4 pb-5">
        {/* Header — tag icon + 채널명 + 연결 테스트 버튼 */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
              <IconTag className="text-icon-primary size-5" />
            </div>
            <h3 className="text-heading-small text-content-normal min-w-0 flex-1 truncate">{channel.name}</h3>
          </div>
          <ChannelTalkConnectionTestButton status={testStatus} />
        </div>

        {/* Access Key + Access Secret (2-column) */}
        <div className="flex gap-3">
          <ChannelField
            label="Access Key"
            value={channel.accessKey}
            placeholder="Access Key 입력하기"
            state={accessKeyState}
          />
          <ChannelField
            label="Access Secret"
            value={channel.accessSecret}
            placeholder="Access Secret 입력하기"
            state={accessSecretState}
          />
        </div>

        {/* Webhook Token */}
        <ChannelField
          label="Webhook Token"
          value={channel.webhookToken}
          placeholder="Webhook Token 입력하기"
          state={webhookTokenState}
        />

        {/* Error 메시지 — error 상태일 때만 표시 */}
        {status === 'error' && channel.errorMessage ? (
          <p className="text-body-xsmall text-status-destructive">{channel.errorMessage}</p>
        ) : null}

        {/* Megaphone 안내 + 동기화 주기 dropdown */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1.5">
            <IconMegaphone className="text-icon-alternative size-4.5 shrink-0" />
            <p className="text-body-xsmall text-content-assistive">{MEGAPHONE_NOTICE}</p>
          </div>
          <ChannelTalkSyncIntervalDropdown variant="channel" value={channel.syncInterval} />
        </div>
      </div>

      {/* 도큐먼트 스페이스 자식 카드들 (있을 때만) */}
      {channel.documentSpaces.length > 0 ? (
        <div className="flex flex-col px-4">
          {channel.documentSpaces.map((ds) => (
            <ChannelTalkDocumentSpaceCard key={ds.id} documentSpace={ds} fieldState="idle" testStatus="idle" />
          ))}
        </div>
      ) : null}

      {/* "도큐먼트 스페이스 추가" 버튼 (default/hover-pressed 2상태) */}
      <div className="px-4 pb-4">
        <button
          type="button"
          onClick={onAddDocumentSpace}
          className="bg-fill-primary-normal-neutral hover:bg-fill-primary-interaction-hover-assistive active:bg-fill-primary-interaction-hover-assistive border-edge-neutral text-body-small text-content-primary flex h-11.5 w-full cursor-pointer items-center justify-center gap-2.5 rounded-lg border px-2.5 py-1.5 transition-colors"
        >
          <IconAdd className="text-icon-primary size-5.5 shrink-0" />
          <span>도큐먼트 스페이스 추가</span>
        </button>
      </div>
    </div>
  );
}

interface ChannelFieldProps {
  label: string;
  value: string;
  placeholder: string;
  state: FieldState;
}

/** 채널 카드의 입력 행 — 라벨 + Required dot + textfield */
function ChannelField({ label, value, placeholder, state }: ChannelFieldProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1.5">
      <div className="flex items-center gap-1">
        <span className="text-body-small text-content-neutral">{label}</span>
        <span className="bg-status-destructive size-[5px] rounded-full" aria-label="필수 입력" />
      </div>
      <ChannelTalkTextField value={value} placeholder={placeholder} state={state} maskable />
    </div>
  );
}
