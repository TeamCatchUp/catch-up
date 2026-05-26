'use client';

// 원문 패널 에러 상태 — 메시지 + 재시도 버튼. ResultErrorState 패턴 차용.

import { motion } from 'motion/react';

import { Button } from '@/shared/components/ui/button';
import { MotionState, panelStateFadeIn } from '@/shared/motion/presets';

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
      variants={panelStateFadeIn}
      className="flex flex-col items-center gap-2 px-5 py-50"
    >
      <p className="text-body-small text-content-alternative text-center">{message}</p>
      <Button variant="text-primary-blue" size="md" onClick={onRetry}>
        다시 시도
      </Button>
    </motion.div>
  );
}
