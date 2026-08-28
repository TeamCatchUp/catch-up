'use client';

import { AnimatePresence, motion } from 'motion/react';

import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { crossfade, crossfadeReduced, MotionState } from '@/shared/motion';
import { cn } from '@/shared/utils/cn';

export interface SideNavMotionFrameProps {
  open: boolean;
  children: React.ReactNode;
}

/**
 * SNB 열림·닫힘 전환 틀. 폭은 사이드 패널과 같은 전환으로 움직이고 내용은 교차 페이드로 바뀐다.
 */
export default function SideNavMotionFrame({ open, children }: SideNavMotionFrameProps) {
  const prefersReducedMotion = usePrefersReducedMotion();

  return (
    <div
      data-slot="side-nav-motion-frame"
      className={cn(
        'relative h-full overflow-hidden',
        !prefersReducedMotion && 'transition-[width] duration-300 ease-out',
      )}
      style={{ width: open ? 'var(--snb-width-open)' : 'var(--snb-width-collapsed)' }}
    >
      {/* wait가 아니면 두 네비가 동시에 마운트돼 나가는 사본이 랜드마크·히트테스트에 남는다 */}
      <AnimatePresence initial={false} mode="wait">
        <motion.div
          key={open ? 'open' : 'collapsed'}
          className="absolute inset-y-0 left-0"
          variants={prefersReducedMotion ? crossfadeReduced : crossfade}
          initial={MotionState.Hidden}
          animate={MotionState.Visible}
          exit={MotionState.Exit}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
