'use client';

import AnswerSkeletonLines from '@/features/chat/components/skeleton/AnswerSkeletonLines';
import PipelineTypeBanner from '@/features/chat/components/skeleton/PipelineTypeBanner';
import type { PipelineQueryType } from '@/features/chat/types';

interface RagAnswerSkeletonProps {
  pipelineType: PipelineQueryType | null;
  pipelineReasoning: string | null;
}

export default function RagAnswerSkeleton({
  pipelineType,
  pipelineReasoning,
}: RagAnswerSkeletonProps) {
  return (
    <div className="flex w-full flex-col gap-5">
      <PipelineTypeBanner pipelineType={pipelineType} pipelineReasoning={pipelineReasoning} />
      <AnswerSkeletonLines />
    </div>
  );
}
