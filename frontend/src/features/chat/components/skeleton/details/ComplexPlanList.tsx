'use client';

import { motion } from 'motion/react';

import type { StepRowEvent } from '@/features/chat/types';
import { fadeInUp, MotionState, staggerListContainer } from '@/shared/motion';
import { cn } from '@/shared/utils/cn';

/** backend가 step별로 `{step, intent}` single dict를 emit (옛 shape Array도 호환). */
interface ComplexPlanListProps {
  items: StepRowEvent[];
}

type PlanEntry = { step: number | string; intent: string };

const isPlanEntry = (x: unknown): x is Partial<PlanEntry> =>
  typeof x === 'object' && x !== null && 'intent' in x;

const extractEntries = (items: StepRowEvent[]): PlanEntry[] => {
  const flat: PlanEntry[] = [];
  for (const item of items) {
    const c = item.content;
    if (!c || typeof c !== 'object') continue;

    if (Array.isArray(c)) {
      // 하위 호환: Array<{step, intent}>
      for (const x of c) {
        if (isPlanEntry(x) && x.intent != null) {
          flat.push({ step: x.step ?? flat.length + 1, intent: String(x.intent) });
        }
      }
    } else if (isPlanEntry(c) && c.intent != null) {
      // backend 신 shape: single {step, intent}
      flat.push({ step: c.step ?? flat.length + 1, intent: String(c.intent) });
    }
  }
  return flat;
};

export default function ComplexPlanList({ items }: ComplexPlanListProps) {
  const entries = extractEntries(items);
  if (!entries.length) return null;

  return (
    <div className="bg-blue-1 border-l-light-blue-5 w-full rounded-xl border-l-[3px] border-solid px-4 py-3">
      <motion.ol
        className="flex flex-col gap-3"
        initial={MotionState.Hidden}
        animate={MotionState.Visible}
        variants={staggerListContainer}
      >
        {entries.map((entry, idx) => {
          const isLast = idx === entries.length - 1;
          return (
            <motion.li
              key={idx}
              variants={fadeInUp}
              className={cn(
                'flex items-center gap-4',
                !isLast && 'border-edge-neutral border-b border-solid pb-3',
              )}
            >
              <span className="bg-information-5 text-content-alternative text-body-xsmall flex h-7 w-7 shrink-0 items-center justify-center rounded-lg">
                {entry.step}
              </span>
              <span className="text-body-xsmall text-content-normal min-w-0 flex-1 break-words">
                {entry.intent}
              </span>
            </motion.li>
          );
        })}
      </motion.ol>
    </div>
  );
}
