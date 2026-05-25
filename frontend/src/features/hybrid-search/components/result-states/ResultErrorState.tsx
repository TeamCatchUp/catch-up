'use client';

// Empty/Loading와 동일한 py-50 + gap-2 패턴으로 시각 통일.

import { motion } from 'motion/react';

import { motionEase, MotionState } from '@/shared/motion/presets';

const fastFadeIn = {
  hidden: { opacity: 0, y: 4 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: motionEase } },
  exit: { opacity: 0, transition: { duration: 0.15, ease: motionEase } },
};

interface ResultErrorStateProps {
  onRetry: () => void;
}

export default function ResultErrorState({ onRetry }: ResultErrorStateProps) {
  return (
    <motion.div
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      exit={MotionState.Exit}
      variants={fastFadeIn}
      className="flex flex-col items-center gap-2 py-50"
    >
      <p className="text-body-small text-content-alternative">
        검색 중 오류가 발생했어요. 다시 시도해주세요.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="text-body-small text-content-primary hover:bg-fill-primary-interaction-hover-assistive cursor-pointer rounded-full px-3 py-1.5 font-medium transition-colors"
      >
        다시 시도
      </button>
    </motion.div>
  );
}
