import type { ReactNode } from 'react';

import { cn } from '@/shared/utils/cn';

export type AgentStatusSectionLabel = '운영중' | '제작중' | '사용 안함';

const STATUS_SECTION_STYLE: Record<
  AgentStatusSectionLabel,
  {
    outerClassName: string;
    labelClassName: string;
  }
> = {
  운영중: {
    outerClassName: 'bg-fill-primary-normal-assistive',
    labelClassName: 'bg-fill-primary-normal-neutral text-text-primary-normal',
  },
  제작중: {
    outerClassName: 'bg-fill-normal-strong',
    labelClassName: 'bg-fill-normal-interaction-disable text-text-normal-normal',
  },
  '사용 안함': {
    outerClassName: 'bg-fill-normal-strong',
    labelClassName: 'bg-fill-normal-interaction-disable text-text-normal-alternative',
  },
};

interface AgentStatusSectionProps {
  label: AgentStatusSectionLabel;
  children: ReactNode;
  className?: string;
}

export default function AgentStatusSection({ label, children, className }: AgentStatusSectionProps) {
  const style = STATUS_SECTION_STYLE[label];

  return (
    <section
      aria-label={`${label} 섹션`}
      className={cn('flex min-w-80 flex-1 flex-col items-start gap-3 rounded-xl p-3', style.outerClassName, className)}
    >
      <span className={cn('text-heading-small w-fit rounded-lg px-2.5 py-1', style.labelClassName)}>{label}</span>
      {children}
    </section>
  );
}
