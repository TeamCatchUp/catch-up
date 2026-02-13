type RagStepKey =
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
type RagUIStepKey = 'router' | 'retrieve' | 'rerank' | 'manage_pr_context' | 'grade' | 'generate';
