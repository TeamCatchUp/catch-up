import type { RagStepKey } from '@/features/chat/types';

interface RagStepSkeletonProps {
  stepKey: RagStepKey;
  label: string;
  Icon: React.ComponentType<{ className?: string }>;
}

const RagStepSkeleton = ({ stepKey, label, Icon }: RagStepSkeletonProps) => {
  const isGenerate = stepKey === 'generate';

  return (
    <div className="flex flex-col gap-8">
      <div className="skeleton-loading-card flex h-20 w-192.75 animate-pulse items-center gap-5 rounded-2xl p-5">
        <div className="border-blue-5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border bg-white">
          <Icon className="h-7 w-7" />
        </div>
        <span className="text-body-medium text-gray-50">{label}</span>
      </div>
      {isGenerate && (
        <div className="flex animate-pulse flex-col gap-5">
          <div className="bg-neutral-1 h-7.5 w-192.75 rounded-lg" />
          <div className="bg-neutral-1 h-7.5 w-147.75 rounded-lg" />
          <div className="bg-neutral-1 h-7.5 w-110.25 rounded-lg" />
          <div className="bg-neutral-1 h-7.5 w-57.75 rounded-lg" />
          <div className="bg-neutral-1 h-7.5 w-29.75 rounded-lg" />
        </div>
      )}
    </div>
  );
};

export default RagStepSkeleton;
