import { describe, expect, it } from 'vitest';

import type { PipelineEvent } from '@/features/chat/types';

import { buildInlineSteps } from './buildInlineSteps';

const simpleEvents: PipelineEvent[] = [
  { node: 'supervisor', status: 'completed', reasoning: '간단한 검색 질문이네요.', content: { query_type: 'simple' } },
  { node: 'generate_vector_queries', status: 'completed', reasoning: '검색어를 만들었어요.' },
  { node: 'search_vector_db', status: 'in_progress', content: [{ vector: 'a', keyword: 'b' }] },
  { node: 'search_vector_db', status: 'completed', reasoning: '100건의 문서를 찾았어요.' },
  { node: 'rerank', status: 'in_progress', reasoning: '관련도순으로 정리할게요.' },
  { node: 'rerank', status: 'completed', content: { source_distribution: {} } },
  { node: 'generate_final_answer', status: 'completed', reasoning: null, content: null },
];

const standardEvents: PipelineEvent[] = [
  {
    node: 'supervisor',
    status: 'completed',
    reasoning: 'API 종류를 묻는 검색 질문이네요.',
    content: { query_type: 'standard' },
  },
  { node: 'rewrite', status: 'in_progress', reasoning: '검색어를 다듬을게요.' },
  { node: 'rewrite', status: 'completed', content: { query: '재작성된 질의' } },
  { node: 'standard_agent', status: 'completed', reasoning: 'API 구조를 찾아보겠습니다.' },
  { node: 'tool_executor', status: 'in_progress', content: { queries: [{ vector: 'a', keyword: 'b' }] } },
  { node: 'tool_executor', status: 'completed', reasoning: '120건의 문서를 찾았어요.' },
  { node: 'tool_executor', status: 'completed', reasoning: '80건의 문서를 찾았어요.' },
  { node: 'rerank', status: 'completed', content: { source_distribution: {} } },
  { node: 'generate_final_answer', status: 'completed', reasoning: null, content: null },
];

const complexEvents: PipelineEvent[] = [
  {
    node: 'supervisor',
    status: 'completed',
    reasoning: '복합 분석이 필요해 보여요.',
    content: { query_type: 'complex' },
  },
  { node: 'rewrite', status: 'in_progress', reasoning: '검색어를 다듬을게요.' },
  { node: 'rewrite', status: 'completed', content: { query: '재작성된 질의' } },
  { node: 'complex_planner', status: 'in_progress', reasoning: '정보 수집 순서를 먼저 정해볼게요.' },
  { node: 'complex_planner', status: 'completed', content: { step: 1, intent: '현재 구현 방식 찾기' } },
  { node: 'complex_planner', status: 'completed', content: { step: 2, intent: '변경 이력 찾기' } },
  { node: 'complex_agent', status: 'completed', reasoning: '단계별 검색을 시작할게요.' },
  { node: 'tool_executor', status: 'completed', reasoning: '240건의 문서를 찾았어요.' },
  { node: 'rerank', status: 'completed', content: { source_distribution: {} } },
  { node: 'generate_final_answer', status: 'completed', reasoning: null, content: null },
];

describe('buildInlineSteps', () => {
  it('simple 파이프라인 → 3단계 (요청 분석·문서 검색·완료)', () => {
    const steps = buildInlineSteps(simpleEvents);
    expect(steps.map((s) => s.title)).toEqual(['요청 분석', '문서 검색', '완료']);
  });

  it('standard 파이프라인 → 4단계 (+ 검색어 재작성)', () => {
    const steps = buildInlineSteps(standardEvents);
    expect(steps.map((s) => s.title)).toEqual(['요청 분석', '검색어 재작성', '문서 검색', '완료']);
  });

  it('complex 파이프라인 → 5단계 (+ 탐색 계획 수립)', () => {
    const steps = buildInlineSteps(complexEvents);
    expect(steps.map((s) => s.title)).toEqual(['요청 분석', '검색어 재작성', '탐색 계획 수립', '문서 검색', '완료']);
  });

  it('검색 completed N개 + reasoning "{X}건" 합산 → "N회 탐색 · 총 M건"', () => {
    const steps = buildInlineSteps(standardEvents);
    const search = steps.find((s) => s.kind === 'search');
    expect(search?.lines).toEqual(['2회 탐색 · 총 200건']);
  });

  it('검색어 재작성은 rewrite content.query를 본문으로 표시', () => {
    const steps = buildInlineSteps(standardEvents);
    expect(steps.find((s) => s.kind === 'rewrite')?.lines).toEqual(['재작성된 질의']);
  });

  it('탐색 계획 수립은 intro reasoning + step 리스트를 누적', () => {
    const steps = buildInlineSteps(complexEvents);
    expect(steps.find((s) => s.kind === 'complex_planner')?.lines).toEqual([
      '정보 수집 순서를 먼저 정해볼게요.',
      '1. 현재 구현 방식 찾기',
      '2. 변경 이력 찾기',
    ]);
  });

  it('검색 단계가 없으면 (direct_answer/clarify/reuse) 빈 배열', () => {
    const directAnswer: PipelineEvent[] = [
      {
        node: 'supervisor',
        status: 'completed',
        reasoning: '바로 답할 수 있어요.',
        content: { query_type: 'direct_answer' },
      },
    ];
    expect(buildInlineSteps(directAnswer)).toEqual([]);
  });

  it('빈 배열 / null / undefined → 빈 배열 (graceful)', () => {
    expect(buildInlineSteps([])).toEqual([]);
    expect(buildInlineSteps(null)).toEqual([]);
    expect(buildInlineSteps(undefined)).toEqual([]);
  });

  it('완료 단계는 최종 답변 노드(generate_final_answer) completed가 없으면 생략', () => {
    const noFinal = simpleEvents.filter((e) => e.node !== 'generate_final_answer');
    const steps = buildInlineSteps(noFinal);
    expect(steps.some((s) => s.kind === 'done')).toBe(false);
  });
});
