type RagStepKey =
  | 'router'
  | 'rewrite'
  | 'plan'
  | 'retrieve'
  | 'rerank'
  | 'manage_pr_context'
  | 'grade'
  | 'generate'
  | 'chitchat';
type RagUIStepKey = 'router' | 'retrieve' | 'rerank' | 'manage_pr_context' | 'grade' | 'generate';
