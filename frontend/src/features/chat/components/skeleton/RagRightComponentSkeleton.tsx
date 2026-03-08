'use client';

import Lottie from 'lottie-react';

import ragSourceLoading from '@/public/lottie/rag-source-loading.json';

interface RagDetailedTasksSkeletonProps {
  message?: string;
}

const RagRightComponentSkeleton = ({ message }: RagDetailedTasksSkeletonProps) => {
  return (
    <div className="mt-2 flex w-full flex-col items-center justify-center gap-5">
      <div className="skeleton-loading-card flex w-full animate-pulse flex-col items-center justify-center gap-5 rounded-2xl p-5">
        <Lottie animationData={ragSourceLoading} loop className="h-23 w-28.75" />
        <span className="text-body-small text-content-assistive whitespace-nowrap">{message}</span>
      </div>
      <div className="flex w-full animate-pulse flex-col gap-5">
        <div className="bg-fill-strong h-7.5 w-full rounded-lg" />
        <div className="bg-fill-strong h-7.5 w-[82%] rounded-lg" />
        <div className="bg-fill-strong h-7.5 w-[71%] rounded-lg" />
        <div className="bg-fill-strong h-7.5 w-[58%] rounded-lg" />
        <div className="bg-fill-strong h-7.5 w-[43%] rounded-lg" />
      </div>
    </div>
  );
};

export default RagRightComponentSkeleton;
