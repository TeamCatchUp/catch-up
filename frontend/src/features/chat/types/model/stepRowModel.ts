/**
 * RAG step history(답변 생성 과정) 도메인 모델.
 *
 * backend `stream_processor.py`가 emit하는 process 이벤트를 row 단위로 누적해
 * 화면에 표시하기 위한 타입.
 */

/**
 * supervisor가 결정하는 파이프라인 분류.
 * - `simple` / `standard` / `complex` / `reuse`: 검색 파이프라인
 * - `direct_answer` / `clarify`: 검색 없는 분기 (RagAnswerSkeleton 마운트 안 됨)
 */
export type PipelineQueryType =
  | 'simple'
  | 'standard'
  | 'complex'
  | 'reuse'
  | 'direct_answer'
  | 'clarify';

/**
 * 한 process emit이 담는 페이로드(노드 단위로 reasoning/content 의미가 다름).
 */
export interface StepRowEvent {
  reasoning: string | null;
  // node × status에 따라 다른 shape — 렌더러에서 narrow
  content: unknown;
}

/**
 * step history의 한 행.
 *
 * 한 노드 호출(in_progress + completed)을 한 row로 묶는다.
 * 같은 노드가 다시 호출되면 새 row가 push된다.
 *
 * `complex_planner`는 예외로 completed가 plan step별 여러 번 emit되므로
 * `completedItems`에 누적된다 (1·2·3·4가 한 박스에 표시되도록).
 */
export interface StepRow {
  id: string;
  node: string;
  inProgress: StepRowEvent | null;
  completedItems: StepRowEvent[];
}
