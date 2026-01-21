type RagStepKey =
  | 'router'
  | 'rewrite'
  | 'plan'
  | 'retrieve'
  | 'manage_pr_context'
  | 'rerank'
  | 'grade'
  | 'generate'
  | 'chitchat';
type RagUIStepKey = 'router' | 'retrieve' | 'rerank' | 'grade' | 'generate';
