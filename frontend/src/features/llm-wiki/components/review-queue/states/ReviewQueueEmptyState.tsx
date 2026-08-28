'use client';

import { motion } from 'motion/react';

import IconEmptyDocument from '@/public/icons/icon/empty_document.svg';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { MotionState, panelStateFadeIn, panelStateFadeInReduced } from '@/shared/motion';

/**
 * 검토할 변경안이 없을 때 상세 자리에 들어가는 안내. 좌측 목록 머리글과 필터는 그대로 남는다.
 * 일러스트 투명도 0.6은 에셋 자체에 들어 있다 — 클래스로 다시 걸면 이중 적용된다.
 */
export default function ReviewQueueEmptyState() {
  const prefersReducedMotion = usePrefersReducedMotion();

  return (
    <motion.div
      variants={prefersReducedMotion ? panelStateFadeInReduced : panelStateFadeIn}
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      className="flex h-full w-full flex-col items-center gap-4 py-30"
    >
      <IconEmptyDocument aria-hidden className="h-13.75 w-16 shrink-0" />
      <p className="text-body-xsmall text-text-normal-assistive text-center">요청된 변경사항이 없어요.</p>
    </motion.div>
  );
}
