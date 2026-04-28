'use client';

import { Button } from '@/shared/components/ui/button';

/**
 * 연결 테스트 버튼의 3가지 상태.
 * - `idle`: 입력 전 / Entered — active 색으로 사용자에게 검증 권유 (`box-soft-primary`)
 * - `active`: Key 수정 중 — 동일한 active 색
 * - `success`: 테스트 성공 — 회색 outline + 라벨만 "테스트 성공"
 *
 * shared `Button` 공통 컴포넌트 + `box-soft-primary` / `box-outline-gray` variant 활용.
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
