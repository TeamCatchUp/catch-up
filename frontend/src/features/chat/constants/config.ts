/** RAG 관련 상수 정의 */

import type { RagUIStepKey } from '@/features/chat/types';

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
 * localStorage 키 생성
 */
export const getStorageKeys = (sessionId: string) => ({
  chat: `chat_${sessionId}`,
});

/**
 * 답변 아이콘 목록
 */
export { RAG_UI_STEPS } from './steps';
