'use client';

import StepRow from '@/features/chat/components/skeleton/StepRow';
import type { StepRow as StepRowModel, StepRowEvent } from '@/features/chat/types';

/**
 * 답변 생성 과정 step history.
 *
 * row 누적 정책은 `upsertStepRow`에 정의됨.
 *
 * Active marker:
 *  - 시각적 마지막 row는 **항상** active marker(파란 concentric circle)로 그린다.
 *  - 한 row의 completed가 도착해도 다음 row가 안 추가되면 그 row가 active로 유지.
 *  - 답변 token 스트림 시작/종료 시까지 마지막 row의 active marker가 유지됨.
 *  - 새 row가 push되는 순간 active가 새 row로 이동.
 *
 * 빈 row 필터링:
 *  - `standard_agent` / `complex_agent` 같은 노드는 reasoning/content 없는 in_progress만 emit하고
 *    completed가 reasoning falsy guard로 인해 안 오는 케이스가 있다.
 *  - 이런 빈 row(시각적으로 빈 줄로 보임)는 step history에서 제외한다.
 */

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
    <div className="flex flex-col">
      {visible.map((row, idx) => {
        const isLast = idx === visible.length - 1;
        // 시각적 마지막 row는 always active. completedItems 도착 여부 무관.
        const isActive = isLast;
        return <StepRow key={row.id} row={row} isActive={isActive} isLast={isLast} />;
      })}
    </div>
  );
}
