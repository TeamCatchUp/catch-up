import type { ReactNode } from 'react';

import { cn } from '@/shared/utils/cn';

export type AgentStatusSectionLabel = '운영중' | '제작중' | '사용 안함';

const STATUS_SECTION_STYLE: Record<
  AgentStatusSectionLabel,
  {
    outerClassName: string;
    headerClassName: string;
    labelClassName: string;
    countClassName: string;
    countTextClassName: string;
  }
> = {
  운영중: {
    outerClassName: 'bg-fill-primary-normal-assistive',
    headerClassName: 'bg-fill-primary-normal-neutral',
    labelClassName: 'text-text-primary-normal',
    countClassName: 'bg-fill-primary-normal-assistive',
    countTextClassName: 'text-text-primary-assistive',
  },
  제작중: {
    outerClassName: 'bg-fill-normal-strong',
    headerClassName: 'bg-fill-normal-interaction-disable',
    labelClassName: 'text-text-normal-normal',
    countClassName: 'bg-fill-normal-interaction-pressed-hover',
    countTextClassName: 'text-text-normal-alternative',
  },
  '사용 안함': {
    outerClassName: 'bg-fill-normal-strong',
    headerClassName: 'bg-fill-normal-interaction-disable',
    labelClassName: 'text-text-normal-alternative',
    countClassName: 'bg-fill-normal-interaction-pressed-hover',
    countTextClassName: 'text-text-normal-alternative',
  },
};

interface AgentStatusSectionProps {
  label: AgentStatusSectionLabel;
  count: number;
  children: ReactNode;
  className?: string;
}

export default function AgentStatusSection({ label, count, children, className }: AgentStatusSectionProps) {
  const style = STATUS_SECTION_STYLE[label];

  return (
    <section
      aria-label={`${label} 섹션`}
      className={cn('flex min-w-80 flex-1 flex-col items-start gap-3 rounded-xl p-3', style.outerClassName, className)}
    >
      <div className={cn('flex w-full items-center gap-2.5 rounded-lg px-3 py-2', style.headerClassName)}>
        <span className={cn('text-heading-small min-w-0 flex-1 truncate', style.labelClassName)}>{label}</span>
        <span
          className={cn(
            'rounded-md2 text-body-small flex min-h-5.75 min-w-5.75 shrink-0 items-center justify-center px-0.5',
            style.countClassName,
            style.countTextClassName,
          )}
        >
          {count}
        </span>
      </div>
      {children}
    </section>
  );
}
