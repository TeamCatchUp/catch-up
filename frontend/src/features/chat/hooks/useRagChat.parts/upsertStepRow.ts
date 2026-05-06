import type { StepRow, StepRowEvent } from '@/features/chat/types';

interface UpsertInput {
  node: string;
  status: 'in_progress' | 'completed' | 'error';
  reasoning: string | null;
  content: unknown;
}

/**
 * - `in_progress` → 항상 새 row.
 * - `completed` → 마지막 row의 같은 노드의 `completedItems`에 push.
 *   `complex_planner`는 step별 누적 허용, 그 외엔 1번만 가능 (이미 받은 노드면 새 row).
 * - `error` → 무시 (호출자가 isError 흐름에서 처리).
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

  return prev;
};
