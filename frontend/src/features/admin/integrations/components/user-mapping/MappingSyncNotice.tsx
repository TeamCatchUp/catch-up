'use client';

import IconError from '@/public/icons/icon/error.svg';
import IconReset from '@/public/icons/icon/reset.svg';
import { Button } from '@/shared/components/ui/button';

type MappingSyncNoticeVariant = 'csv-required' | 'partial-failure';

interface MappingSyncNoticeProps {
  variant: MappingSyncNoticeVariant;
  /** "2026. 2. 9. 01:31" 형태 — 없으면 표기 생략. API 필드는 배선 때 확정(감사 C-5) */
  lastSyncedAt?: string | null;
  /** partial-failure 전용 — "동기화 재시도" */
  onRetry?: () => void;
}

const MESSAGES: Record<MappingSyncNoticeVariant, string> = {
  'csv-required': 'CSV 파일을 업로드해주세요!',
  'partial-failure': '일부 유저 동기화에 실패했습니다.',
};

/**
 * 매핑 표 위의 동기화 안내 배너 — 구버전 승계(사용자 승인 2026-08-04).
 * 부분 실패 변형에만 "마지막 동기화 {시각}"과 [동기화 재시도] 버튼이 붙는다.
 */
export default function MappingSyncNotice({ variant, lastSyncedAt, onRetry }: MappingSyncNoticeProps) {
  return (
    <div className="bg-accent-red-lighten flex items-center gap-4 rounded-lg px-4 py-2.5">
      <IconError aria-hidden="true" className="text-accent-red-default size-5 shrink-0" />
      <p className="text-body-small text-accent-red-default min-w-0 flex-1 truncate">{MESSAGES[variant]}</p>

      {variant === 'partial-failure' && (
        <>
          {lastSyncedAt && (
            <p className="text-body-xsmall text-text-normal-alternative shrink-0 whitespace-nowrap">
              마지막 동기화 <span className="text-text-normal-neutral">{lastSyncedAt}</span>
            </p>
          )}
          {onRetry && (
            <Button variant="text-secondary-mono" size="sm" onClick={onRetry} className="shrink-0">
              <IconReset className="size-4" />
              동기화 재시도
            </Button>
          )}
        </>
      )}
    </div>
  );
}
