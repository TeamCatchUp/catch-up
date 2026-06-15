'use client';

import { cn } from '@/shared/utils/cn';

import { BODY_SERVICE_COLUMN_CLASS } from '../../../../constants/memberUiConfig';
import type { UnlinkedStatus } from '../../../../utils/usersTableHelpers';

interface UnusedTagCellProps {
  /** '미사용' | '미등록' — '완료'는 이 셀에 안 옴 (selectCellMode가 보장). */
  status: UnlinkedStatus;
}

/** mode='unused-tag' 셀 — inline 회색 태그. */
export default function UnusedTagCell({ status }: UnusedTagCellProps) {
  return (
    <div className={cn(BODY_SERVICE_COLUMN_CLASS, 'items-center')}>
      <span className="bg-fill-normal-interaction-hover text-body-xsmall text-text-normal-alternative rounded-md2 inline-flex items-center justify-center px-1.5 py-0.5">
        {status === '미사용' ? '미사용' : '-'}
      </span>
    </div>
  );
}
