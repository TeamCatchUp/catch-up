import type { StepRow, StepRowEvent } from '@/features/chat/types';

interface UpsertInput {
  node: string;
  status: 'in_progress' | 'completed' | 'error';
  reasoning: string | null;
  content: unknown;
}

/**
 * stream_processor의 process 이벤트를 step row 배열에 누적한다.
 *
 * 누적 정책 (결정 4 A2 + 결정 8 B1):
 * - `in_progress` 도착 → 항상 새 row push.
 * - `completed` 도착 →
 *   - 마지막 row의 노드가 일치하고:
 *     - `complex_planner`이면 `completedItems`에 누적 push (1·2·3·4 step list가 한 박스에 들어감).
 *     - `completedItems.length === 0` (해당 호출의 in_progress만 받은 상태)이면 같은 row의 `completedItems`에 push (1개).
 *   - 그 외 → 새 row push.
 *
 * `error`는 호출자에서 별도 처리(결정 13 G3 — 무시)되므로 여기 도달하지 않는다.
 */
export const upsertStepRow = (prev: StepRow[], input: UpsertInput): StepRow[] => {
  const { node, status, reasoning, content } = input;
  const event: StepRowEvent = { reasoning, content };

  if (status === 'in_progress') {
    return [
      ...prev,
      {
        id: `${node}-${prev.length}`,
        node,
        inProgress: event,
        completedItems: [],
      },
    ];
  }

  if (status === 'completed') {
    const last = prev[prev.length - 1];
    const sameNode = last && last.node === node;
    const canMergeIntoLast =
      sameNode && (node === 'complex_planner' || last.completedItems.length === 0);

    if (canMergeIntoLast) {
      const next = prev.slice(0, -1);
      next.push({
        ...last,
        completedItems: [...last.completedItems, event],
      });
      return next;
    }

    return [
      ...prev,
      {
        id: `${node}-${prev.length}`,
        node,
        inProgress: null,
        completedItems: [event],
      },
    ];
  }

  // error 등은 호출자에서 제외 — 안전 fallback
  return prev;
};
