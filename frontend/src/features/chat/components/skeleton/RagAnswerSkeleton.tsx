'use client';

import AnswerSkeletonLines from '@/features/chat/components/skeleton/AnswerSkeletonLines';
import PipelineTypeBanner from '@/features/chat/components/skeleton/PipelineTypeBanner';
import type { PipelineQueryType } from '@/features/chat/types';

/**
 * 답변 본문 영역에 마운트되는 skeleton.
 *
 * 결정 1 D + 사용자 추가 정정:
 *  - 답변 본문(메시지 wrapper):
 *      [PipelineTypeBanner 한 줄 헤더] + [AnswerSkeletonLines 5줄 placeholder]
 *  - 사이드바(RagSidebar): TopicHeader + StepHistory (chip 박스 포함)
 *
 * 결정 10 D1: 호출자가 simple/standard/complex일 때만 마운트한다.
 * 호출자(RagAnswer)가 답변 token 첫 도착 시점부터 unmount.
 */

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
