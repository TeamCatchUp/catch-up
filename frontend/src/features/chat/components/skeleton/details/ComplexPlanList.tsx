'use client';

import type { StepRowEvent } from '@/features/chat/types';
import { cn } from '@/shared/utils/cn';

/**
 * complex_planner 노드 completedItems의 step 리스트를 1·2·3·4 박스로 정렬.
 *
 * Figma: 12861-55042 (Complex 프레임 complex_planner 행)
 * - 외곽: bg #f7fbff (blue-1) + border 1px #eaebec + 좌측 3px border #e5f6fe (light-blue-5) + radius 12 + px-4 py-3
 * - 각 step row 사이 border-b #eaebec (마지막 제외)
 * - 28×28 number badge: bg #e7f4fe (information-5) + rounded-lg(8px) + text 13px Medium #6d7882
 * - intent text: 13px Medium #33363d (content-normal)
 *
 * 입력 형태 (2가지 정규화):
 *  - 각 completed emit의 `content: {step, intent}` single dict (backend 신 shape)
 *  - 하위 호환: `content: Array<{step, intent}>` (옛 shape)
 */

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
      <ol className="flex flex-col gap-3">
        {entries.map((entry, idx) => {
          const isLast = idx === entries.length - 1;
          return (
            <li
              key={idx}
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
            </li>
          );
        })}
      </ol>
    </div>
  );
}
