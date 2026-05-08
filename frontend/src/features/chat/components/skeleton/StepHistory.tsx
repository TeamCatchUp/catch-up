'use client';

import { motion } from 'motion/react';

import StepRow from '@/features/chat/components/skeleton/StepRow';
import type { StepRow as StepRowModel, StepRowEvent } from '@/features/chat/types';
import { fadeInUp, MotionState, staggerListContainer } from '@/shared/motion';

interface StepHistoryProps {
  rows: StepRowModel[];
}

const hasEventPayload = (e: StepRowEvent | null | undefined): boolean => {
  if (!e) return false;
  if (e.reasoning) return true;
  const c = e.content;
  if (c == null) return false;
  if (typeof c === 'string') return c.length > 0;
  if (Array.isArray(c)) return c.length > 0;
  if (typeof c === 'object') return Object.keys(c as object).length > 0;
  return Boolean(c);
};

const isVisibleRow = (row: StepRowModel): boolean => {
  if (hasEventPayload(row.inProgress)) return true;
  return row.completedItems.some(hasEventPayload);
};

export default function StepHistory({ rows }: StepHistoryProps) {
  const visible = rows.filter(isVisibleRow);
  if (!visible.length) return null;

  return (
    <motion.div
      className="flex flex-col"
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      variants={staggerListContainer}
    >
      {visible.map((row, idx) => {
        const isLast = idx === visible.length - 1;
        const isActive = isLast;
        return (
          <motion.div key={row.id} variants={fadeInUp}>
            <StepRow row={row} isActive={isActive} isLast={isLast} />
          </motion.div>
        );
      })}
    </motion.div>
  );
}
