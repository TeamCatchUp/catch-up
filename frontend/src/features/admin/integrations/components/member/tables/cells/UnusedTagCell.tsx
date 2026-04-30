'use client';

import { cn } from '@/shared/utils/cn';

import { BODY_SERVICE_COLUMN_CLASS } from '../../../../constants/memberUiConfig';
import type { MemberIntegrationStatus } from '../../../../types/integrationModel';

interface UnusedTagCellProps {
  /** '미사용' | '미등록' — '완료'는 이 셀에 안 옴. 채널톡 read-only 케이스는 항상 '미사용'. */
  status: MemberIntegrationStatus;
}

/**
 * mode='unused-tag' 셀 — Figma Tag 컴포넌트 시안 (inline 회색 태그).
 * 채널톡 read-only도 동일 시각.
 */
export default function UnusedTagCell({ status }: UnusedTagCellProps) {
  return (
    <div className={cn(BODY_SERVICE_COLUMN_CLASS, 'items-center')}>
      <span className="bg-fill-interaction-hover text-body-xsmall text-content-alternative rounded-md2 inline-flex items-center justify-center px-1.5 py-0.5">
        {status === '미사용' ? '미사용' : '-'}
      </span>
    </div>
  );
}
