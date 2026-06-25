import type { ReactNode } from 'react';

import { cn } from '@/shared/utils/cn';

interface HelpExampleBoxProps {
  children: ReactNode;
  badgeLabel?: string;
  className?: string;
}

export default function HelpExampleBox({ children, badgeLabel = '예시', className }: HelpExampleBoxProps) {
  return (
    <div
      className={cn(
        'border-line-normal-assistive bg-fill-normal-strong flex flex-col gap-3 rounded-xl border px-5 py-4',
        className,
      )}
    >
      <span className="bg-fill-normal-interaction-hover text-body-xsmall text-text-normal-alternative rounded-md2 w-fit px-1.5 py-0.5">
        {badgeLabel}
      </span>
      <div className="text-reading-label-rg-medium text-text-normal-normal flex flex-col gap-3">{children}</div>
    </div>
  );
}
