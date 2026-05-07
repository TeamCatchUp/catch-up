import { describe, expect, it } from 'vitest';

import { upsertStepRow } from './upsertStepRow';

describe('upsertStepRow', () => {
  it('in_progress 도착 시 새 row가 push된다', () => {
    const next = upsertStepRow([], {
      node: 'rewrite',
      status: 'in_progress',
      reasoning: '어떤 답을 원하시는지 헤아려볼게요.',
      content: null,
    });
    expect(next).toHaveLength(1);
    expect(next[0]).toMatchObject({
      node: 'rewrite',
      inProgress: { reasoning: '어떤 답을 원하시는지 헤아려볼게요.', content: null },
      completedItems: [],
    });
  });

  it('같은 노드의 in_progress 직후 completed는 같은 row에 합쳐진다 (A2)', () => {
    let rows = upsertStepRow([], {
      node: 'rewrite',
      status: 'in_progress',
      reasoning: '...',
      content: null,
    });
    rows = upsertStepRow(rows, {
      node: 'rewrite',
      status: 'completed',
      reasoning: null,
      content: '재구성된 질문',
    });
    expect(rows).toHaveLength(1);
    expect(rows[0].inProgress).not.toBeNull();
    expect(rows[0].completedItems).toHaveLength(1);
    expect(rows[0].completedItems[0].content).toBe('재구성된 질문');
  });

  it('같은 노드가 다시 호출되면 새 row가 push된다 (loop/retry)', () => {
    let rows = upsertStepRow([], {
      node: 'tool_executor',
      status: 'in_progress',
      reasoning: null,
      content: [{ vector: 'q1', keyword: [] }],
    });
    rows = upsertStepRow(rows, {
      node: 'tool_executor',
      status: 'completed',
      reasoning: '120건의 문서를 찾았어요.',
      content: null,
    });
    rows = upsertStepRow(rows, {
      node: 'tool_executor',
      status: 'in_progress',
      reasoning: null,
      content: [{ vector: 'q2', keyword: [] }],
    });
    expect(rows).toHaveLength(2);
    expect(rows[0].completedItems[0].reasoning).toBe('120건의 문서를 찾았어요.');
    expect(rows[1].inProgress?.content).toEqual([{ vector: 'q2', keyword: [] }]);
  });

  it('complex_planner는 completed가 여러 번 와도 같은 row에 누적된다 (B1)', () => {
    // backend 신 shape: 각 emit이 single {step, intent} dict
    let rows = upsertStepRow([], {
      node: 'complex_planner',
      status: 'in_progress',
      reasoning: '정보 수집 순서를 정해볼게요.',
      content: null,
    });
    rows = upsertStepRow(rows, {
      node: 'complex_planner',
      status: 'completed',
      reasoning: null,
      content: { step: 1, intent: '첫 단계' },
    });
    rows = upsertStepRow(rows, {
      node: 'complex_planner',
      status: 'completed',
      reasoning: null,
      content: { step: 2, intent: '둘째 단계' },
    });
    rows = upsertStepRow(rows, {
      node: 'complex_planner',
      status: 'completed',
      reasoning: null,
      content: { step: 3, intent: '셋째 단계' },
    });
    expect(rows).toHaveLength(1);
    expect(rows[0].completedItems).toHaveLength(3);
  });

  it('error status는 row 변경 없이 그대로 반환한다 (G3)', () => {
    const initial = upsertStepRow([], {
      node: 'supervisor',
      status: 'in_progress',
      reasoning: null,
      content: null,
    });
    const next = upsertStepRow(initial, {
      node: 'supervisor',
      status: 'error',
      reasoning: '질문 의도 파악 실패',
      content: null,
    });
    expect(next).toEqual(initial);
  });

  it('이미 completed된 노드 뒤에 같은 노드 completed가 또 와도 새 row를 만든다 (sanity)', () => {
    let rows = upsertStepRow([], {
      node: 'standard_agent',
      status: 'completed',
      reasoning: 'first',
      content: null,
    });
    rows = upsertStepRow(rows, {
      node: 'standard_agent',
      status: 'completed',
      reasoning: 'second',
      content: null,
    });
    expect(rows).toHaveLength(2);
  });
});
