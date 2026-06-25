'use client';

// user_chat 이 아닌 카드 선택 시 원문 패널에 표시되는 '준비 중' 안내.
// toolName 은 호출부가 선택 카드 소스로 보간한 협업 툴 표시명.

import { motion } from 'motion/react';

import { MotionState, panelStateFadeIn } from '@/shared/motion/presets';

interface OriginalPanelComingSoonProps {
  toolName: string;
}

export default function OriginalPanelComingSoon({ toolName }: OriginalPanelComingSoonProps) {
  return (
    <motion.div
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      exit={MotionState.Exit}
      variants={panelStateFadeIn}
      className="flex flex-col items-center gap-1 px-5 py-50 text-center"
    >
      <p className="text-heading-small text-text-normal-alternative font-semibold">
        곧 <strong className="text-text-normal-normal font-semibold">{toolName}</strong>의 내용도 Catch Up에서 만나볼 수
        있어요.
      </p>
      <p className="text-body-small text-text-normal-assistive">열심히 준비중이니 조금만 기다려주세요:)</p>
    </motion.div>
  );
}
