'use client';

// 원문 패널 에러 상태 — 메시지 + 재시도 버튼. ResultErrorState 패턴 차용.

import { motion } from 'motion/react';

import { Button } from '@/shared/components/ui/button';
import { motionEase, MotionState } from '@/shared/motion/presets';

const fastFadeIn = {
  hidden: { opacity: 0, y: 4 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: motionEase } },
  exit: { opacity: 0, transition: { duration: 0.15, ease: motionEase } },
};

interface OriginalPanelErrorProps {
  message: string;
  onRetry: () => void;
}

export default function OriginalPanelError({ message, onRetry }: OriginalPanelErrorProps) {
  return (
    <motion.div
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      exit={MotionState.Exit}
      variants={fastFadeIn}
      className="flex flex-col items-center gap-2 px-5 py-50"
    >
      <p className="text-body-small text-content-alternative text-center">{message}</p>
      <Button variant="text-primary-blue" size="md" onClick={onRetry}>
        다시 시도
      </Button>
    </motion.div>
  );
}
