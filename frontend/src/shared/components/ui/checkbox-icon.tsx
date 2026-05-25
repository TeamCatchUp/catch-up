'use client';

import CheckboxChecked from '@/public/icons/icon/checkbox_checked.svg';
import CheckboxUnchecked from '@/public/icons/icon/checkbox_unchecked.svg';
import { cn } from '@/shared/utils/cn';

interface CheckboxIconProps {
  checked: boolean;
  /** SVG 아이콘 크기 (e.g., "size-5", "size-6") */
  className?: string;
}

/** SVG 기반 체크박스 아이콘 (hover 시 원형 배경 효과) */
export default function CheckboxIcon({ checked, className }: CheckboxIconProps) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full p-1 transition-colors',
        checked ? 'hover:bg-fill-primary-interaction-hover-assistive' : 'hover:bg-fill-interaction-hover',
      )}
    >
      {checked ? (
        <CheckboxChecked className={cn('text-icon-primary shrink-0', className)} />
      ) : (
        <CheckboxUnchecked className={cn('text-content-assistive shrink-0', className)} />
      )}
    </span>
  );
}
