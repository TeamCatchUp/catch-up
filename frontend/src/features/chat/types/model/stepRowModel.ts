export type PipelineQueryType =
  | 'simple'
  | 'standard'
  | 'complex'
  | 'reuse'
  | 'direct_answer'
  | 'clarify';

export interface StepRowEvent {
  reasoning: string | null;
  content: unknown;
}

/**
 * 한 노드 호출(in_progress + completed)을 한 row로 묶는다.
 * `complex_planner`만 예외 — completed가 step별로 여러 번 emit되어 `completedItems`에 누적.
 */
export interface StepRow {
  id: string;
  node: string;
  inProgress: StepRowEvent | null;
  completedItems: StepRowEvent[];
}
