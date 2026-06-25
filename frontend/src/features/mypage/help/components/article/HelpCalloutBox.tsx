import type { ReactNode } from 'react';

import { cn } from '@/shared/utils/cn';

interface HelpCalloutBoxProps {
  children: ReactNode;
  className?: string;
}

export default function HelpCalloutBox({ children, className }: HelpCalloutBoxProps) {
  return (
    <div
      className={cn(
        'border-line-normal-assistive bg-fill-normal-strong text-reading-label-rg-medium text-text-normal-normal flex flex-col gap-3 rounded-xl border px-5 py-4',
        className,
      )}
    >
      {children}
    </div>
  );
}
