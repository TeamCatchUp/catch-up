'use client';

// 제어형 접기/펴기 primitive. open 상태는 호출부가 소유.

import type { ReactNode } from 'react';
import { AnimatePresence, motion } from 'motion/react';

import { collapseExpand, MotionState } from '@/shared/motion';

interface CollapsibleProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  header: ReactNode;
  children: ReactNode;
}

export default function Collapsible({ open, onOpenChange, header, children }: CollapsibleProps) {
  return (
    <div className="flex w-full flex-col">
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        aria-expanded={open}
        className="flex w-full cursor-pointer"
      >
        {header}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="panel"
            variants={collapseExpand}
            initial={MotionState.Hidden}
            animate={MotionState.Visible}
            exit={MotionState.Exit}
            className="w-full overflow-hidden"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
