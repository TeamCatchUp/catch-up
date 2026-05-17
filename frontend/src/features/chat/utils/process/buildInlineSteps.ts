import type { PipelineEvent } from '@/features/chat/types';

export type InlineStepIcon = 'request' | 'rewrite' | 'plan' | 'search' | 'done';

export interface InlineStep {
  kind: 'supervisor' | 'rewrite' | 'complex_planner' | 'search' | 'done';
  title: string;
  icon: InlineStepIcon;
  lines: string[];
}

// 검색 단계로 집계할 노드 (simple은 search_vector_db, standard/complex는 tool_executor)
const SEARCH_NODES = new Set(['tool_executor', 'search_vector_db']);

// 파이프라인 터미널 노드 — 이 노드 completed가 곧 "완료"
const FINAL_ANSWER_NODES = new Set(['generate_final_answer', 'generate_final_answer_fast']);

const isCompleted = (e: PipelineEvent) => e.status === 'completed';

// reasoning 문자열의 "{N}건" 패턴 — 모듈 레벨로 hoist (호출마다 재생성 회피)
const DOC_COUNT_PATTERN = /(\d+)\s*건/;

// reasoning 문자열의 "{N}건"에서 숫자 추출
const parseDocCount = (text: string | null | undefined): number => {
  if (!text) return 0;
  const matched = text.match(DOC_COUNT_PATTERN);
  return matched ? Number(matched[1]) : 0;
};

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;

/**
 * pipeline_result(노드별 진행 이벤트 배열)를 인라인 표시용 단계 목록으로 변환한다.
 * - 존재하는 노드만 단계로 변환 → simple 3 / standard 4 / complex 5단계
 * - 검색 단계가 없으면 RAG 파이프라인이 아님(direct_answer/clarify/reuse) → 빈 배열
 */
export const buildInlineSteps = (events: PipelineEvent[] | null | undefined): InlineStep[] => {
  if (!Array.isArray(events) || events.length === 0) return [];

  const searchCompleted = events.filter((e) => SEARCH_NODES.has(e.node) && isCompleted(e));
  if (searchCompleted.length === 0) return [];

  const steps: InlineStep[] = [];

  // 1. 요청 분석 — supervisor completed reasoning
  const supervisor = events.find((e) => e.node === 'supervisor' && isCompleted(e));
  if (supervisor?.reasoning) {
    steps.push({ kind: 'supervisor', title: '요청 분석', icon: 'request', lines: [supervisor.reasoning] });
  }

  // 2. 검색어 재작성 — rewrite completed content.query (문자열 또는 { query } dict 모두 수용)
  const rewrite = events.find((e) => e.node === 'rewrite' && isCompleted(e));
  if (rewrite) {
    const query =
      typeof rewrite.content === 'string' ? rewrite.content : (asRecord(rewrite.content)?.query as string | undefined);
    if (query) {
      steps.push({ kind: 'rewrite', title: '검색어 재작성', icon: 'rewrite', lines: [query] });
    }
  }

  // 3. 탐색 계획 수립 — complex_planner in_progress reasoning + completed { step, intent } 누적
  const plannerEvents = events.filter((e) => e.node === 'complex_planner');
  if (plannerEvents.length > 0) {
    const lines: string[] = [];
    const intro = plannerEvents.find((e) => e.status === 'in_progress')?.reasoning;
    if (intro) lines.push(intro);
    plannerEvents
      .filter(isCompleted)
      .map((e) => asRecord(e.content))
      .filter((c): c is Record<string, unknown> => c !== null && 'intent' in c)
      .forEach((c, idx) => {
        const step = typeof c.step === 'number' ? c.step : idx + 1;
        lines.push(`${step}. ${String(c.intent)}`);
      });
    if (lines.length > 0) {
      steps.push({ kind: 'complex_planner', title: '탐색 계획 수립', icon: 'plan', lines });
    }
  }

  // 4. 문서 검색 — 검색 completed 이벤트 수 · reasoning "{N}건" 합산
  const totalDocs = searchCompleted.reduce((sum, e) => sum + parseDocCount(e.reasoning), 0);
  steps.push({
    kind: 'search',
    title: '문서 검색',
    icon: 'search',
    lines: [`${searchCompleted.length}회 탐색 · 총 ${totalDocs}건`],
  });

  // 5. 완료 — 최종 답변 생성 노드 completed 도달 시
  if (events.some((e) => FINAL_ANSWER_NODES.has(e.node) && isCompleted(e))) {
    steps.push({ kind: 'done', title: '완료', icon: 'done', lines: [] });
  }

  return steps;
};
