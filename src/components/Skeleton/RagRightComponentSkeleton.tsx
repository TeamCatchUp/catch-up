import SourceFile from '/public/icons/icon/source-file.svg';

interface RagDetailedTasksSkeletonProps {
  message?: string;
}

const RagRightComponentSkeleton = ({ message }: RagDetailedTasksSkeletonProps) => {
  return (
    <div className="mt-3 flex w-115 flex-col items-center justify-center gap-5">
      <div className="bg-blue-1 flex w-105 animate-pulse flex-col items-center justify-center gap-5 rounded-2xl p-5">
        <SourceFile className="h-23 w-28.75" />
        <span className="text-body-small text-gray-30 whitespace-nowrap">{message}</span>
      </div>
      <div className="flex animate-pulse flex-col gap-5">
        <div className="bg-neutral-1 h-7.5 w-107 rounded-lg"></div>
        <div className="bg-neutral-1 h-7.5 w-85.75 rounded-lg"></div>
        <div className="bg-neutral-1 h-7.5 w-74.5 rounded-lg"></div>
        <div className="bg-neutral-1 h-7.5 w-60.75 rounded-lg"></div>
        <div className="bg-neutral-1 h-7.5 w-44.5 rounded-lg"></div>
      </div>
    </div>
  );
};

export default RagRightComponentSkeleton;
