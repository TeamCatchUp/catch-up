'use client';

import CheckboxChecked from '@/public/icons/icon/checkbox_checked.svg';
import CheckboxIndeterminate from '@/public/icons/icon/checkbox_indeterminate.svg';
import CheckboxUnchecked from '@/public/icons/icon/checkbox_unchecked.svg';
import { cn } from '@/shared/utils/cn';

interface CheckboxIconProps {
  checked: boolean;
  /** 일부만 선택된 상태. `checked`보다 우선한다 */
  indeterminate?: boolean;
  /** SVG 아이콘 크기 (e.g., "size-5", "size-6") */
  className?: string;
  /** 원형 hover 영역의 padding 조정 (e.g., "p-1.5"). 기본 p-1 */
  wrapperClassName?: string;
}

/** SVG 기반 체크박스 아이콘 (hover 시 원형 배경 효과) */
export default function CheckboxIcon({ checked, indeterminate, className, wrapperClassName }: CheckboxIconProps) {
  const active = indeterminate || checked;

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full p-1 transition-colors',
        active ? 'hover:bg-fill-primary-normal-interaction-hover-assistive' : 'hover:bg-fill-normal-interaction-hover',
        wrapperClassName,
      )}
    >
      {indeterminate ? (
        <CheckboxIndeterminate className={cn('text-icon-primary-normal shrink-0', className)} />
      ) : checked ? (
        <CheckboxChecked className={cn('text-icon-primary-normal shrink-0', className)} />
      ) : (
        <CheckboxUnchecked className={cn('text-text-normal-assistive shrink-0', className)} />
      )}
    </span>
  );
}
