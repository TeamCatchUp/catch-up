'use client';

import Lottie from 'lottie-react';

import ragSourceLoading from '@/public/lottie/rag-source-loading.json';

interface RagDetailedTasksSkeletonProps {
  message?: string;
}

const SKELETON_LINE_WIDTHS = ['100%', '82%', '71%', '58%', '43%'];
const STAGGER_MS = 260;

export default function RagRightComponentSkeleton({ message }: RagDetailedTasksSkeletonProps) {
  return (
    <div className="mt-2 flex w-full flex-col items-center justify-center gap-5">
      <div className="skeleton-loading-card flex w-full flex-col items-center justify-center gap-5 rounded-2xl p-5">
        <Lottie animationData={ragSourceLoading} loop className="h-23 w-28.75" />
        <span className="text-body-small text-content-assistive whitespace-nowrap">{message}</span>
      </div>
      <div className="animate-breath flex w-full flex-col gap-5">
        {SKELETON_LINE_WIDTHS.map((w, i) => (
          <div
            key={i}
            aria-hidden
            className="animate-line-drop bg-fill-strong h-7.5 rounded-lg"
            style={{ width: w, animationDelay: `${i * STAGGER_MS}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
