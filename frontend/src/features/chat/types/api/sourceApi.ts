/**
 * REST 응답에서 사용하는 단순 소스 타입.
 * @interface SourceResponseApi
 */
export interface SourceResponseApi {
  source_type: 'file' | 'wiki' | 'url' | 'github' | 'slack' | 'comment';
  content: string;
  file_path?: string;
  html_url?: string;
  language?: string;
}

/**
 * 백엔드 소스 플랫폼 타입.
 * - catchup/rag/schemas/sources.py SourceType 기준
 */
export type BackendSourceSourceApi = 'jira' | 'slack' | 'github' | 'unknown';

/**
 * 백엔드 소스 엔티티 타입.
 * - catchup/rag/schemas/sources.py EntityType(+ code) 기준
 */
export type BackendSourceEntityTypeApi =
  | 'issue'
  | 'epic'
  | 'message'
  | 'pr'
  | 'comment'
  | 'code';

/**
 * 백엔드 RAG 소스 원본 타입.
 * 스트리밍/정규화 과정에서 공통으로 사용하는 핵심 계약 타입.
 * @interface BackendSourceApi
 */
export interface BackendSourceApi {
  index?: number;
  is_cited?: boolean;
  source: BackendSourceSourceApi;
  entity_type: BackendSourceEntityTypeApi;
  relevance_score?: number;
  html_url?: string;
  url?: string;
  content?: string;
  text?: string;
  citation_rationale?: string;
  owner?: string;

  // github
  repo?: string;
  file_path?: string;
  days_ago?: number;
  title?: string;
  pr_number?: number;
  number?: number;
  created_at?: number | string;
  updated_at?: number | string;
  author?: string;

  // jira
  issue_key?: string;
  summary?: string;
  project_name?: string;
  project_key?: string;
  parent_key?: string;
  parent_summary?: string;
  assignee_name?: string;
  assignee?: string;
  status_id?: number;
  status?: string;

  // slack
  channel_name?: string;
  team_id?: string;
  ts?: string;
  thread_ts?: string;
}
