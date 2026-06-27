import { Skeleton } from '@/shared/components/ui/skeleton';
import { cn } from '@/shared/utils/cn';

import type { AgentStudioFilter } from '../../../types/agentStudioModel';
import type { AgentStatusSectionLabel } from '../content/AgentStatusSection';

const STATUS_SECTION_SKELETON_STYLE: Record<
  AgentStatusSectionLabel,
  {
    outerClassName: string;
    headerClassName: string;
    labelClassName: string;
  }
> = {
  운영중: {
    outerClassName: 'bg-fill-primary-normal-assistive',
    headerClassName: 'bg-fill-primary-normal-neutral',
    labelClassName: 'text-text-primary-normal',
  },
  제작중: {
    outerClassName: 'bg-fill-normal-strong',
    headerClassName: 'bg-fill-normal-interaction-disable',
    labelClassName: 'text-text-normal-normal',
  },
  '사용 안함': {
    outerClassName: 'bg-fill-normal-strong',
    headerClassName: 'bg-fill-normal-interaction-disable',
    labelClassName: 'text-text-normal-alternative',
  },
};

const STATUS_LABELS = ['운영중', '제작중', '사용 안함'] as const satisfies readonly AgentStatusSectionLabel[];
const GRID_SKELETON_COUNT = 3;

interface AgentStudioListSkeletonProps {
  selectedFilter: AgentStudioFilter;
}

function AgentCardSkeleton({ layout = 'section' }: { layout?: 'section' | 'grid' }) {
  return (
    <article
      aria-label="Agent 카드 로딩"
      aria-busy="true"
      className={cn(
        'border-line-normal-normal bg-fill-normal-assistive-dark flex flex-col overflow-hidden rounded-xl border p-5',
        layout === 'grid' ? 'min-w-80 flex-none basis-[calc((100%_-_48px)/3)]' : 'w-full',
      )}
    >
      <div className="flex w-full flex-col gap-5">
        <div className="flex w-full flex-col gap-3">
          <div className="flex h-7 w-full items-center gap-3">
            <Skeleton className="h-6 min-w-0 flex-1" />
            <Skeleton className="size-7 shrink-0 rounded-full" />
          </div>
          <div className="flex w-full flex-col gap-1.5">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-4/5" />
          </div>
        </div>
        <div className="flex h-6 items-center gap-2">
          <Skeleton className="size-6.25 shrink-0 rounded-full" />
          <Skeleton className="h-4 w-14 shrink-0" />
          <Skeleton className="size-1 shrink-0 rounded-full" />
          <Skeleton className="h-4 w-10 shrink-0" />
          <Skeleton className="h-4 w-22 shrink-0" />
        </div>
      </div>
    </article>
  );
}

function AgentStatusSectionSkeleton({ label }: { label: AgentStatusSectionLabel }) {
  const style = STATUS_SECTION_SKELETON_STYLE[label];

  return (
    <section
      aria-label={`${label} 로딩 섹션`}
      aria-busy="true"
      className={cn('flex min-w-80 flex-1 flex-col items-start gap-3 rounded-xl p-3', style.outerClassName)}
    >
      <div className={cn('flex w-full items-center gap-2.5 rounded-lg px-3 py-2', style.headerClassName)}>
        <span className={cn('text-heading-small min-w-0 flex-1 truncate', style.labelClassName)}>{label}</span>
        <Skeleton className="rounded-md2 h-5.75 w-5.75 shrink-0" />
      </div>
      <AgentCardSkeleton />
    </section>
  );
}

export default function AgentStudioListSkeleton({ selectedFilter }: AgentStudioListSkeletonProps) {
  if (selectedFilter !== 'all') {
    return Array.from({ length: GRID_SKELETON_COUNT }, (_, index) => (
      <AgentCardSkeleton key={`agent-card-skeleton-${index}`} layout="grid" />
    ));
  }

  return STATUS_LABELS.map((label) => <AgentStatusSectionSkeleton key={label} label={label} />);
}
