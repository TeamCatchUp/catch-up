/** RAG 관련 상수 정의 */

/**
 * 백엔드 노드 이름 -> UI 단계 매핑
 * null은 UI에 표시하지 않는 노드를 의미
 */
export const NODE_TO_UI_STEP: Record<string, RagUIStepKey | null> = {
  route: 'router',
  router: 'router',
  rewrite: 'router',
  generate_vector_queries: 'retrieve',
  search_vector_db: 'retrieve',
  expand_graph_context: 'retrieve',
  fetch_details_after_graph_context_expansion: 'retrieve',
  fallback_cypher_query: 'retrieve',
  plan: 'retrieve',
  retrieve: 'retrieve',
  rerank: 'rerank',
  manage_pr_context: null,
  grade: 'grade',
  generate_final_answer: 'generate',
  generate: 'generate',
  chitchat: 'generate',
} as const;

/**
 * 팀 스페이스 옵션
 */
export const TEAM_SPACES = [
  { id: 'fe', name: 'Catch Up | FE' },
  { id: 'be', name: 'Catch Up | BE' },
  { id: 'pm', name: 'Catch Up | 기획' },
  { id: 'design', name: 'Catch Up | Design' },
] as const;

export type TeamSpace = (typeof TEAM_SPACES)[number];

/**
 * 인덱스 리스트 (하드코딩된 값 - 추후 동적으로 변경 예정)
 */
export const HARD_CODED_INDEX_LIST = [
  'CatchUp_BE_develop_code',
  'CatchUp_BE_develop_pr',
  'cu_jira_issue',
] as const;


/**
 * SSE 설정
 */
export const SSE_CONFIG = {
  /** 연결 타임아웃 (ms) */
  TIMEOUT_MS: 30000,
} as const;

/**
 * localStorage 키 생성
 */
export const getStorageKeys = (sessionId: string) => ({
  chat: `chat_${sessionId}`,
});

/**
 * 답변 아이콘 목록
 */
export { RAG_UI_STEPS } from './steps';
