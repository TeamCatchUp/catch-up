'use client';

import IconBook from '@/public/icons/icon/book.svg';

import type {
  ChannelTalkDocumentSpace,
  ChannelTalkFieldState,
  ChannelTalkTestButtonStatus,
} from '../../../types/channelTalkModel';
import ChannelTalkConnectionTestButton from './ChannelTalkConnectionTestButton';
import ChannelTalkSyncIntervalDropdown from './ChannelTalkSyncIntervalDropdown';
import ChannelTalkTextField from './ChannelTalkTextField';

interface ChannelTalkDocumentSpaceCardProps {
  documentSpace: ChannelTalkDocumentSpace;
  /** 텍스트필드 시각 변형 (부모 channel의 connectionStatus에 종속) */
  fieldState?: ChannelTalkFieldState;
  /** 연결 테스트 버튼 상태 */
  testStatus?: ChannelTalkTestButtonStatus;
  onUpdate: (patch: Partial<ChannelTalkDocumentSpace>) => void;
}

/**
 * 채널톡 도큐먼트 스페이스 카드 — 채널 하위 항목.
 *
 * 채널과 달리 Webhook Token이 없고 Access Key + Access Secret + 동기화 주기만 입력.
 * 좌측 column의 vertical line은 다음 도큐먼트 스페이스 카드와 시각적으로 연결.
 */
export default function ChannelTalkDocumentSpaceCard({
  documentSpace,
  fieldState = 'idle',
  testStatus = 'idle',
  onUpdate,
}: ChannelTalkDocumentSpaceCardProps) {
  return (
    <div className="flex w-full items-start gap-4 pb-5">
      {/* Left column: book icon (32×32) + vertical line connector — 카드 높이에 따라 자동 신장 */}
      <div className="flex shrink-0 flex-col items-center gap-5 self-stretch pt-5">
        <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
          <IconBook className="text-icon-primary size-5" />
        </div>
        <div className="bg-edge-neutral w-px flex-1" aria-hidden />
      </div>

      {/* Right column: input form (604px) — 상단 border-t로 채널/이전 카드와 구분 */}
      <div className="border-edge-neutral flex min-w-0 flex-1 flex-col gap-5 border-t pt-5">
        {/* Header — 이름 + 연결 테스트 버튼 */}
        <div className="flex flex-wrap items-center justify-between gap-x-10 gap-y-2">
          <h4 className="text-heading-small text-content-normal min-w-0 flex-1 truncate">{documentSpace.name}</h4>
          <ChannelTalkConnectionTestButton status={testStatus} />
        </div>

        {/* Access Key + Access Secret (2-column) */}
        <div className="flex gap-3">
          <DocumentSpaceField
            label="Access Key"
            value={documentSpace.accessKey}
            placeholder="Access Key 입력하기"
            state={fieldState}
            onChange={(next) => onUpdate({ accessKey: next })}
          />
          <DocumentSpaceField
            label="Access Secret"
            value={documentSpace.accessSecret}
            placeholder="Access Secret 입력하기"
            state={fieldState}
            onChange={(next) => onUpdate({ accessSecret: next })}
          />
        </div>

        {/* Sync interval dropdown */}
        <ChannelTalkSyncIntervalDropdown
          variant="documentSpace"
          value={documentSpace.syncInterval}
          onChange={(next) => onUpdate({ syncInterval: next })}
        />
      </div>
    </div>
  );
}

interface DocumentSpaceFieldProps {
  label: string;
  value: string;
  placeholder: string;
  state: ChannelTalkFieldState;
  onChange: (next: string) => void;
}

/** 도큐먼트 스페이스 입력 행 — 라벨 + Required dot + textfield */
function DocumentSpaceField({ label, value, placeholder, state, onChange }: DocumentSpaceFieldProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1.5">
      <div className="flex items-center gap-1">
        <span className="text-body-small text-content-neutral">{label}</span>
        <span className="bg-status-destructive size-[5px] rounded-full" aria-label="필수 입력" />
      </div>
      <ChannelTalkTextField value={value} placeholder={placeholder} state={state} maskable onChange={onChange} />
    </div>
  );
}
