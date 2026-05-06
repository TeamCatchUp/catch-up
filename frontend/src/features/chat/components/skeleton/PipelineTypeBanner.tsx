'use client';

import type { PipelineQueryType } from '@/features/chat/types';

/**
 * 답변 생성 과정 헤더 한 줄.
 * Figma: 12587-52126 (fileKey 7UwupbVvmHkElmP2OBJQio)
 *
 * 시각: border 1px #e1e2e4 / radius 12px / padding 12px / gap 12px
 *      라벨(13px, blue) + 멘트(15px, normal)
 */

interface PipelineTypeBannerProps {
  pipelineType: PipelineQueryType | null;
  pipelineReasoning: string | null;
}

const LABEL_BY_TYPE: Record<PipelineQueryType, string> = {
  simple: 'Simple',
  standard: 'Standard',
  complex: 'Complex',
  reuse: 'Reuse',
  direct_answer: 'Direct',
  clarify: 'Clarify',
};

export default function PipelineTypeBanner({
  pipelineType,
  pipelineReasoning,
}: PipelineTypeBannerProps) {
  if (!pipelineType) return null;

  const label = LABEL_BY_TYPE[pipelineType];

  return (
    <div className="border-edge-neutral flex items-center gap-3 overflow-hidden rounded-xl border border-solid p-3">
      <span className="text-body-xsmall text-content-primary-assistive shrink-0 truncate">
        {label}
      </span>
      <span className="text-body-small text-content-normal min-w-0 flex-1 truncate">
        {pipelineReasoning ?? ''}
      </span>
    </div>
  );
}
