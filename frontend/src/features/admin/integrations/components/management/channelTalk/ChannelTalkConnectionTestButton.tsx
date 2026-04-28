'use client';

import { cn } from '@/shared/utils/cn';

/**
 * 연결 테스트 버튼의 3가지 상태 (Figma node `12004:101461` 매핑).
 * - `idle`: 입력 전 / Entered — 회색 (`bg-fill-interaction-inactive` + `text-content-assistive`)
 * - `active`: Key 수정 중 — 파란색 active (`bg-fill-primary-normal-neutral` + `text-content-primary`)
 * - `success`: 테스트 성공 — 회색 + 라벨만 "테스트 성공"
 */
type ConnectionTestButtonStatus = 'idle' | 'active' | 'success';

interface ChannelTalkConnectionTestButtonProps {
  status?: ConnectionTestButtonStatus;
  onClick?: () => void;
  disabled?: boolean;
}

const STATUS_LABELS: Record<ConnectionTestButtonStatus, string> = {
  idle: '연결 테스트하기',
  active: '연결 테스트하기',
  success: '테스트 성공',
};

/** 채널톡 채널 카드 헤더의 "연결 테스트하기" 박스 버튼 (3상태) */
export default function ChannelTalkConnectionTestButton({
  status = 'idle',
  onClick,
  disabled,
}: ChannelTalkConnectionTestButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'text-body-xsmall flex h-7.5 min-w-9 cursor-pointer items-center justify-center gap-1 rounded-lg border px-2 py-1 transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        status === 'active'
          ? 'bg-fill-primary-normal-neutral border-edge-neutral text-content-primary'
          : 'bg-fill-interaction-inactive border-edge-normal text-content-assistive',
      )}
    >
      {STATUS_LABELS[status]}
    </button>
  );
}
