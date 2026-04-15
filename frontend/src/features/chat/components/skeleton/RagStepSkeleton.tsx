import type { RagStepKey } from '@/features/chat/types';

interface RagStepSkeletonProps {
  stepKey: RagStepKey;
  label: string;
  Icon: React.ComponentType<{ className?: string }>;
}

export default function RagStepSkeleton({ stepKey, label, Icon }: RagStepSkeletonProps) {
  const isGenerate = stepKey === 'generate';

  return (
    <div className="flex flex-col gap-2.5">
      <div className="skeleton-loading-card flex h-14.5 w-full animate-pulse items-center gap-2.5 rounded-2xl px-5 py-4">
        <Icon className="size-5" />
        <span className="text-body-medium text-content-alternative">{label}</span>
      </div>
      {isGenerate && (
        <div className="flex animate-pulse flex-col gap-5">
          <div className="bg-fill-strong h-7.5 w-192.75 rounded-lg" />
          <div className="bg-fill-strong h-7.5 w-147.75 rounded-lg" />
          <div className="bg-fill-strong h-7.5 w-110.25 rounded-lg" />
          <div className="bg-fill-strong h-7.5 w-57.75 rounded-lg" />
          <div className="bg-fill-strong h-7.5 w-29.75 rounded-lg" />
        </div>
      )}
    </div>
  );
}
