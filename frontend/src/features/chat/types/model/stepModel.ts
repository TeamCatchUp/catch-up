/**
 * 백엔드 노드 기준 RAG 전체 단계 키.
 */
export type RagStepKeyModel =
  | 'route'
  | 'router'
  | 'rewrite'
  | 'generate_vector_queries'
  | 'search_vector_db'
  | 'expand_graph_context'
  | 'fetch_details_after_graph_context_expansion'
  | 'fallback_cypher_query'
  | 'plan'
  | 'retrieve'
  | 'rerank'
  | 'manage_pr_context'
  | 'grade'
  | 'generate_final_answer'
  | 'generate'
  | 'chitchat';

/**
 * 프론트 UI에서 노출하는 축약 단계 키.
 */
export type RagUIStepKeyModel = 'router' | 'retrieve' | 'rerank' | 'manage_pr_context' | 'grade' | 'generate';
