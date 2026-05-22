'use client';

// 원문 패널 빈 상태 — 결과 0건이거나 선택된 카드가 없을 때.

import { motion } from 'motion/react';

import { motionEase, MotionState } from '@/shared/motion/presets';

const fastFadeIn = {
  hidden: { opacity: 0, y: 4 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: motionEase } },
  exit: { opacity: 0, transition: { duration: 0.15, ease: motionEase } },
};

export default function OriginalPanelEmpty() {
  return (
    <motion.div
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      exit={MotionState.Exit}
      variants={fastFadeIn}
      className="flex flex-col items-center gap-1 px-5 py-50"
    >
      <p className="text-heading-small text-content-alternative font-semibold">
        표시할 원문이 없어요.
      </p>
      <p className="text-body-small text-content-assistive text-center">
        검색 결과에서 대화를 선택하면 원문을 볼 수 있어요.
      </p>
    </motion.div>
  );
}
