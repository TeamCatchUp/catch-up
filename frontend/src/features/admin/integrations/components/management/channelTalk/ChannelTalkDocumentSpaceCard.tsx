'use client';

import IconBook from '@/public/icons/icon/book.svg';

import type { ChannelTalkDocumentSpace } from '../../../types/channelTalkModel';
import ChannelTalkConnectionTestButton from './ChannelTalkConnectionTestButton';
import ChannelTalkSyncIntervalDropdown from './ChannelTalkSyncIntervalDropdown';
import ChannelTalkTextField from './ChannelTalkTextField';

interface ChannelTalkDocumentSpaceCardProps {
  documentSpace: ChannelTalkDocumentSpace;
  /** 텍스트필드 시각 변형 (부모 channel의 connectionStatus에 종속) */
  fieldState?: 'idle' | 'error' | 'focus';
  /** 연결 테스트 버튼 상태 */
  testStatus?: 'idle' | 'active' | 'success';
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
}: ChannelTalkDocumentSpaceCardProps) {
  return (
    <div className="flex w-full gap-4 py-5">
      {/* Left column: book icon (32×32) + vertical line connector */}
      <div className="relative flex w-8 shrink-0 flex-col items-center">
        <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
          <IconBook className="text-icon-primary size-5" />
        </div>
        <div className="bg-edge-neutral absolute top-13 h-[139px] w-px" aria-hidden />
      </div>

      {/* Right column: input form (604px) */}
      <div className="flex min-w-0 flex-1 flex-col gap-5">
        {/* Header — 이름 + 연결 테스트 버튼 */}
        <div className="flex items-center justify-between gap-4">
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
          />
          <DocumentSpaceField
            label="Access Secret"
            value={documentSpace.accessSecret}
            placeholder="Access Secret 입력하기"
            state={fieldState}
          />
        </div>

        {/* Sync interval dropdown */}
        <ChannelTalkSyncIntervalDropdown variant="documentSpace" value={documentSpace.syncInterval} />
      </div>
    </div>
  );
}

interface DocumentSpaceFieldProps {
  label: string;
  value: string;
  placeholder: string;
  state: 'idle' | 'error' | 'focus';
}

/** 도큐먼트 스페이스 입력 행 — 라벨 + Required dot + textfield */
function DocumentSpaceField({ label, value, placeholder, state }: DocumentSpaceFieldProps) {
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
