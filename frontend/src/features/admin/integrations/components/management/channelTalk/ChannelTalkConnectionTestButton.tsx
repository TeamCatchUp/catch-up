'use client';

import { Button } from '@/shared/components/ui/button';

import type { ChannelTalkTestButtonStatus } from '../../../types/channelTalkModel';

/**
 * shared `Button` 공통 컴포넌트 + `box-soft-primary` / `box-outline-gray` variant 활용.
 * - `idle` / `active`: active 색으로 검증 권유 (box-soft-primary)
 * - `success`: 회색 outline + 라벨 "테스트 성공"
 */

interface ChannelTalkConnectionTestButtonProps {
  status?: ChannelTalkTestButtonStatus;
  onClick?: () => void;
  disabled?: boolean;
}

const STATUS_LABELS: Record<ChannelTalkTestButtonStatus, string> = {
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
    <Button
      variant={status === 'success' ? 'box-outline-gray' : 'box-soft-primary'}
      size="sm"
      onClick={onClick}
      disabled={disabled}
    >
      {STATUS_LABELS[status]}
    </Button>
  );
}
